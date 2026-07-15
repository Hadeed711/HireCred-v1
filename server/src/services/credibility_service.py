import asyncio
import uuid
import logging
from datetime import datetime
from pathlib import Path
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.database import AsyncSessionLocal
from src.models.credibility_score import CredibilityScore, FraudRisk
from src.models.profile import Profile
from src.ai.credibility_prompt import evaluate_profile
from src.ai.cv_prompt import analyze_cv
from src.services.authenticity_service import check_profile_authenticity, compute_url_warnings
from src.services.cv_extractor import extract_cv_text_and_sections, compute_cv_profile_match
from src.services.validation_service import validate_cv_text
from src.routers.leaderboard import invalidate_leaderboard_cache

# Limit concurrent outbound URL checks to avoid exhausting the connection pool
_URL_CHECK_SEM = asyncio.Semaphore(5)

_CV_DIR = Path(__file__).parent.parent.parent / "uploads" / "cv"
# Bump to invalidate previously cached cv_analysis payloads
_CV_ANALYSIS_VERSION = 2

# LLM budgets. Generous on purpose: nothing holds a DB connection while these
# run, and a CPU-only Ollama box needs the headroom (see task_manager notes).
_CV_AI_TIMEOUT = 30.0
_SCORING_AI_TIMEOUT = 30.0

logger = logging.getLogger(__name__)


async def _analyze_cv_file(
    cv_file_path: str | None,
    cached: dict | None,
    user_id: uuid.UUID,
) -> tuple[dict | None, bool]:
    """
    Produce the cv_analysis payload for the uploaded CV.

    Runs pdfplumber extraction + heuristic authenticity checks + the Ollama
    CV prompt, and caches everything (including a text excerpt used for the
    profile-match check) in the cv_analysis JSONB column.

    A cached result is reused only when the AI step actually succeeded
    (`ai_enriched`); an extraction-only result from an Ollama outage is
    retried on the next rescore.

    Returns (cv_analysis, changed) — `changed` is True when a fresh analysis
    was computed and must be persisted.
    """
    if not cv_file_path:
        return None, False

    if (
        cached
        and cached.get("version") == _CV_ANALYSIS_VERSION
        and cached.get("ai_enriched", False)
    ):
        return cached, False

    cv_path = _CV_DIR / cv_file_path
    try:
        pdf_bytes = await asyncio.to_thread(cv_path.read_bytes)
    except OSError as exc:
        logger.warning("CV file unreadable for user %s: %s", user_id, exc)
        return None, False

    extracted = await asyncio.to_thread(extract_cv_text_and_sections, pdf_bytes)

    is_authentic = True
    rejection_reason = ""
    text_err = validate_cv_text(extracted["text"])
    if text_err:
        is_authentic = False
        rejection_reason = text_err.message

    ai_data: dict = {}
    try:
        ai_data = await asyncio.wait_for(
            analyze_cv(extracted["text"], extracted["sections"]), timeout=_CV_AI_TIMEOUT
        )
    except Exception as exc:
        reason = str(exc).strip() or exc.__class__.__name__
        logger.warning("CV AI analysis unavailable (%s); using extraction-only data", reason)

    if ai_data and not ai_data.get("is_authentic", True):
        is_authentic = False
        rejection_reason = rejection_reason or ai_data.get("rejection_reason", "CV appears to be a template.")

    analysis = {
        "version": _CV_ANALYSIS_VERSION,
        "ai_enriched": bool(ai_data),
        "extracted_skills": ai_data.get("extracted_skills", []),
        "experience_summary": ai_data.get("experience_summary", ""),
        "cv_title": ai_data.get("cv_title", ""),
        "is_authentic": is_authentic,
        "rejection_reason": rejection_reason,
        "sections": extracted["sections"],
        "word_count": extracted["word_count"],
        "text_excerpt": extracted["text"][:3000],
    }
    return analysis, True


def _rule_based_score(profile_data: dict) -> dict:
    """Fallback scoring when Ollama is unavailable. Rewards profile completeness."""
    score = 15
    strengths = []
    risks = []

    auth_flags = profile_data.get("authenticity_flags") or []

    if profile_data.get("bio"):
        bio_words = len(str(profile_data.get("bio") or "").split())
        score += 8 if bio_words >= 50 else 4
        strengths.append("Has a profile bio")
        if bio_words < 15:
            risks.append("Bio is very short")
    else:
        risks.append("No bio provided")

    skills = profile_data.get("skills", [])
    score += min(len(skills) * 2, 10)
    if len(skills) >= 3:
        strengths.append(f"Lists {len(skills)} skills")
    elif len(skills) == 0:
        risks.append("No skills listed")

    experience = profile_data.get("experience", [])
    score += min(len(experience) * 8, 16)
    if len(experience) >= 1:
        strengths.append(f"Has {len(experience)} work experience entr{'y' if len(experience) == 1 else 'ies'}")
    else:
        risks.append("No experience listed")

    portfolio = profile_data.get("portfolio", [])
    score += min(len(portfolio) * 6, 12)
    if len(portfolio) >= 1:
        strengths.append(f"Showcases {len(portfolio)} portfolio project{'s' if len(portfolio) > 1 else ''}")

    proof_signals = profile_data.get("proof_signals", [])
    score += min(len(proof_signals) * 4, 12)
    if len(proof_signals) >= 1:
        strengths.append(f"Submitted {len(proof_signals)} proof signal{'s' if len(proof_signals) > 1 else ''}")
    else:
        risks.append("No proof signals added")

    cv = profile_data.get("cv_analysis") or {}
    cv_match = profile_data.get("cv_match") or {}
    if cv.get("is_authentic"):
        score += 6
        strengths.append("CV uploaded and verified")
        if cv_match.get("passed"):
            score += 6
            strengths.append("CV content matches profile claims")

    return {
        "credibility_score": min(score, 100),
        "strengths": strengths,
        "risks": risks,
        "fraud_flags": [],
    }


async def _check_urls_async(portfolio: list[dict], proof_signals: list[dict]) -> list[str]:
    """Run async URL reachability checks and return human-readable warnings."""
    from src.services.url_checker import check_url
    warnings: list[str] = []

    urls_to_check: list[tuple[str, str]] = []
    for item in portfolio:
        u = item.get("url") or ""
        if u:
            urls_to_check.append((item.get("title", "portfolio item"), u))
    for sig in proof_signals:
        u = sig.get("url") or ""
        if u:
            urls_to_check.append((sig.get("title", "proof signal"), u))

    async def _guarded_check(url: str) -> dict:
        async with _URL_CHECK_SEM:
            return await check_url(url)

    results = await asyncio.gather(
        *[_guarded_check(u) for _, u in urls_to_check],
        return_exceptions=True,
    )
    for (label, url), result in zip(urls_to_check, results):
        if isinstance(result, Exception):
            continue
        if not result.get("reachable"):
            warnings.append(
                f'URL for "{label}" is not reachable: {result.get("note", "unknown error")}.'
            )
        elif result.get("title_suspicious"):
            warnings.append(
                f'URL for "{label}" leads to a dead/parked page (title: "{result.get("page_title", "")}") — '
                "this link may be fake."
            )

    return warnings


async def compute_and_save_score(user_id: uuid.UUID) -> dict | None:
    """
    Compute and persist a credibility score in three phases:

      1. Short-lived read session — snapshot all profile data.
      2. Slow evidence gathering (CV analysis, URL checks, LLM scoring) with
         NO database connection held. Holding a session open across 30-60s of
         AI work lets the server/proxy kill the idle connection, which used
         to abort the whole pipeline at commit time.
      3. Fresh write session — persist cv_analysis + upsert the score row.
    """
    # ── Phase 1: read snapshot ────────────────────────────────────────────
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Profile)
            .where(Profile.user_id == user_id)
            .options(selectinload(Profile.proof_signals), selectinload(Profile.user))
        )
        profile = result.scalar_one_or_none()
        if not profile:
            return None

        owner_name = profile.user.full_name
        owner_email = profile.user.email
        proof_signals_data = [
            {
                "signal_type": ps.signal_type.value,
                "title": ps.title,
                "url": ps.url,
                "description": ps.description,
            }
            for ps in profile.proof_signals
        ]
        snapshot = {
            "title": profile.title,
            "location": profile.location,
            "bio": profile.bio,
            "skills": profile.skills or [],
            "experience": profile.experience or [],
            "portfolio": profile.portfolio or [],
            "cv_file_path": profile.cv_file_path,
            "cv_analysis": profile.cv_analysis,
        }

    try:
        # ── Phase 2: gather evidence (no DB session held) ─────────────────

        # Step 1: CV analysis (extraction + AI + profile match)
        has_cv = bool(snapshot["cv_file_path"])
        cv_analysis, cv_changed = await _analyze_cv_file(
            snapshot["cv_file_path"], snapshot["cv_analysis"], user_id
        )

        cv_match: dict | None = None
        if cv_analysis:
            cv_match = compute_cv_profile_match(
                {
                    "text": cv_analysis.get("text_excerpt", ""),
                    "sections": cv_analysis.get("sections", []),
                    "word_count": cv_analysis.get("word_count", 0),
                },
                {
                    "title": snapshot["title"],
                    "skills": snapshot["skills"],
                    "experience": snapshot["experience"],
                },
            )

        # Step 2: Authenticity heuristic checks
        auth_result = check_profile_authenticity(
            {
                "bio": snapshot["bio"],
                "title": snapshot["title"],
                "location": snapshot["location"],
                "skills": snapshot["skills"],
                "experience": snapshot["experience"],
                "portfolio": snapshot["portfolio"],
            },
            owner_email=owner_email,
            owner_name=owner_name,
        )

        # Step 3: URL reachability check
        url_warnings_async = await _check_urls_async(snapshot["portfolio"], proof_signals_data)
        url_warnings_format = compute_url_warnings(snapshot["portfolio"], proof_signals_data)
        all_url_warnings = list(dict.fromkeys(url_warnings_async + url_warnings_format))

        # Step 4: Build full profile_data for AI scoring
        profile_data = {
            "owner_name": owner_name,
            "title": snapshot["title"],
            "location": snapshot["location"],
            "bio": snapshot["bio"],
            "skills": snapshot["skills"],
            "experience": snapshot["experience"],
            "portfolio": snapshot["portfolio"],
            "proof_signals": proof_signals_data,
            "has_cv": has_cv,
            "cv_analysis": cv_analysis,
            "cv_match": cv_match,
            "authenticity_flags": auth_result["flags"],
            "url_warnings": all_url_warnings,
        }

        # Step 5: AI scoring (with full evidence context)
        try:
            score_data = await asyncio.wait_for(
                evaluate_profile(profile_data), timeout=_SCORING_AI_TIMEOUT
            )
            if score_data.get("credibility_score") == 0 and not score_data.get("strengths"):
                raise RuntimeError("AI returned a zero score with no strengths")
        except Exception as exc:
            reason = str(exc).strip() or exc.__class__.__name__
            logger.warning("AI scoring failed for user %s (%s); using rule-based fallback", user_id, reason)
            score_data = _rule_based_score(profile_data)

        # Step 6: Apply authenticity penalty on top of AI score
        raw_score = score_data["credibility_score"]
        auth_penalty = auth_result["penalty"]
        if auth_penalty > 0:
            raw_score = max(0, raw_score - auth_penalty)
            score_data["risks"] = score_data.get("risks", []) + [
                f"Authenticity penalty ({auth_penalty} pts): " + "; ".join(auth_result["flags"][:2])
            ]

        # Step 7: Apply URL warning penalty
        if len(all_url_warnings) >= 1:
            raw_score = max(0, raw_score - min(len(all_url_warnings) * 2, 8))

        # Step 7b: CV authenticity / profile-match penalty
        cv_match_warnings = list(cv_match["warnings"]) if cv_match else []
        if cv_analysis and not cv_analysis.get("is_authentic", True):
            raw_score = max(0, raw_score - 12)
            reason = cv_analysis.get("rejection_reason") or "CV appears to be placeholder content."
            score_data["risks"] = score_data.get("risks", []) + [f"CV rejected: {reason}"]
        elif cv_match and not cv_match["passed"] and cv_match_warnings:
            raw_score = max(0, raw_score - min(4 + 2 * len(cv_match_warnings), 10))
            score_data["risks"] = score_data.get("risks", []) + [
                "CV does not match the profile: " + cv_match_warnings[0]
            ]

        score_data["credibility_score"] = max(0, min(100, raw_score))

        # Step 8: Determine is_suspicious / fraud_risk
        is_suspicious = auth_result["risk_level"] in ("medium", "high")
        fraud_flags = score_data.get("fraud_flags", [])
        if len(fraud_flags) >= 2 or auth_result["risk_level"] == "high" or auth_penalty >= 25:
            fraud_risk = FraudRisk.high
        elif len(fraud_flags) >= 1 or auth_result["risk_level"] == "medium" or auth_penalty >= 12:
            fraud_risk = FraudRisk.medium
        else:
            fraud_risk = FraudRisk.low

        # ── Phase 3: persist on a fresh connection ────────────────────────
        upsert_values = {
            "user_id": user_id,
            "score": score_data["credibility_score"],
            "strengths": score_data.get("strengths", []),
            "risks": score_data.get("risks", []),
            "fraud_risk": fraud_risk,
            "fraud_flags": fraud_flags,
            "is_suspicious": is_suspicious,
            "authenticity_flags": auth_result["flags"],
            "cv_match_score": cv_match["match_score"] if cv_match else None,
            "cv_match_warnings": cv_match_warnings,
            "url_warnings": all_url_warnings,
            "computed_at": datetime.utcnow(),
        }
        upsert_stmt = (
            pg_insert(CredibilityScore)
            .values(**upsert_values)
            .on_conflict_do_update(
                index_elements=["user_id"],
                set_={k: v for k, v in upsert_values.items() if k != "user_id"},
            )
        )

        async with AsyncSessionLocal() as db:
            try:
                if cv_changed:
                    await db.execute(
                        update(Profile)
                        .where(Profile.user_id == user_id)
                        .values(cv_analysis=cv_analysis)
                    )
                await db.execute(upsert_stmt)
                await db.commit()
            except Exception:
                await db.rollback()
                raise

        invalidate_leaderboard_cache()
        logger.info(
            "Credibility score computed for user %s: %d (authenticity_penalty=%d, has_cv=%s, cv_match=%s)",
            user_id, score_data["credibility_score"], auth_penalty, has_cv,
            cv_match["match_score"] if cv_match else "n/a",
        )
        return score_data

    except Exception:
        logger.exception("Failed to compute credibility score for user %s", user_id)
        return None
