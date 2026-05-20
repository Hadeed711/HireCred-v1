"""
Profile credibility scoring prompt — optimised for fast local inference.
Uses the JSON-prefix technique so the model computes its own score
instead of copying the example value (a known small-LLM failure mode).
"""
import logging
from datetime import datetime, timezone
from src.ai.ollama_client import call_ollama, extract_json

logger = logging.getLogger(__name__)

# NO example score in the system prompt — we use the prefix technique instead.
_SYSTEM = """You are HireCred, a professional hiring-trust scoring AI.
Analyze the candidate profile below and score it from 0 to 100.

Scoring criteria (total 100 pts):
- Profile completeness: 18 pts
- Skill vs experience alignment: 22 pts
- Portfolio quality (real URLs, specific descriptions): 22 pts
- Writing clarity and professionalism: 8 pts
- Proof signals (GitHub, portfolio, references): 18 pts
- CV uploaded: 12 pts (0 if no CV)

Important rules:
- AUTH FLAGS listed below are confirmed red flags — deduct 5 to 8 points per flag. Do NOT collapse the entire score.
- URL WARNINGS are dead or unreachable links — deduct 3 pts per warning.
- Dummy, placeholder, or fictional content in ONE specific section → deduct 5 to 8 points for that section only. Other genuine sections MUST still earn their full points.
- Sci-fi content, fictional dates, joke skills, or impossible claims in a SINGLE section → subtract 6 to 8 pts from that section's contribution only, not the whole score.
- Only if the ENTIRE profile is fabricated across ALL sections should the total score be very low.
- Good, genuine, and detailed sections must always be scored on their own merit regardless of other sections having issues.
- Strengths and risks: write max 6 words each, max 2 items each.
- fraud_flags: only if there is clear evidence of deception across multiple sections.
- Compute a UNIQUE score based on THIS profile's actual content."""

# JSON prefix — model must fill in the number, cannot copy an example
_JSON_PREFIX = '{"credibility_score":'


async def evaluate_profile(profile_data: dict) -> dict:
    """Call Ollama to score the profile using the JSON-prefix technique."""
    prompt = _build_prompt(profile_data)
    try:
        raw = await call_ollama(prompt, num_predict=200)

        # The model responds starting right after {"credibility_score":
        # Reconstruct the full JSON so the parser can read it
        text = raw.strip()
        if not text.startswith("{"):
            text = _JSON_PREFIX + text

        data = _safe_extract_json(text)
        data["credibility_score"] = max(0, min(100, int(data.get("credibility_score", 0))))
        # Strip empty strings the model occasionally emits
        data["strengths"] = [s for s in data.get("strengths", []) if isinstance(s, str) and s.strip()]
        data["risks"] = [r for r in data.get("risks", []) if isinstance(r, str) and r.strip()]
        data["fraud_flags"] = [f for f in data.get("fraud_flags", []) if isinstance(f, str) and f.strip()]

        logger.info("AI score computed: %d | strengths=%d risks=%d flags=%d",
                    data["credibility_score"], len(data["strengths"]),
                    len(data["risks"]), len(data["fraud_flags"]))
        return data
    except Exception as exc:
        logger.warning("Ollama scoring failed [%s]: %s", type(exc).__name__, exc)
        raise RuntimeError(f"Ollama scoring failed [{type(exc).__name__}]: {exc}") from exc


def _safe_extract_json(text: str) -> dict:
    """
    Parse JSON from model output robustly.
    Handles: markdown fences, leading/trailing prose, nested duplicates.
    """
    import json as _json

    # Pass 1: standard extractor (handles markdown fences)
    try:
        return extract_json(text)
    except Exception:
        pass

    # Pass 2: find the innermost complete {...} block that is valid JSON
    depth = 0
    start_i = -1
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start_i = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start_i >= 0:
                candidate = text[start_i:i + 1]
                try:
                    data = _json.loads(candidate)
                    if "credibility_score" in data:
                        return data
                except Exception:
                    pass
                start_i = -1  # reset and keep scanning

    raise ValueError(f"Could not parse JSON from model output: {text[:200]!r}")


def _build_prompt(d: dict) -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m")
    lines = [_SYSTEM, f"\n--- CANDIDATE PROFILE (scored on {today}) ---"]

    # ── Core fields ────────────────────────────────────────────────────────────
    lines.append(f"Title: {(d.get('title') or 'Not provided')[:60]}")
    lines.append(f"Location: {(d.get('location') or 'Not provided')[:40]}")
    bio = (d.get("bio") or "").strip()
    lines.append(f"Bio ({len(bio.split())} words): {bio[:200]}" if bio else "Bio: Not provided")

    skills = d.get("skills") or []
    lines.append(f"Skills ({len(skills)}): {', '.join(skills[:15])}" if skills else "Skills: None")

    # ── Experience ─────────────────────────────────────────────────────────────
    experience = (d.get("experience") or [])[:3]
    if experience:
        lines.append(f"Experience ({len(experience)} roles):")
        for exp in experience:
            dates = f"{exp.get('start_date','?')}-{'present' if exp.get('current') else (exp.get('end_date') or '?')}"
            lines.append(f"  [{dates}] {exp.get('title','?')} at {exp.get('company','?')}")
            desc = (exp.get("description") or "").strip()
            if desc:
                lines.append(f"    Desc: {desc[:120]}")
    else:
        lines.append("Experience: None listed")

    # ── Portfolio ──────────────────────────────────────────────────────────────
    portfolio = (d.get("portfolio") or [])[:3]
    if portfolio:
        lines.append(f"Portfolio ({len(portfolio)} items):")
        for item in portfolio:
            lines.append(f"  - {item.get('title','?')}: {(item.get('description') or 'no description')[:100]}")
            if item.get("url"):
                lines.append(f"    URL: {item['url'][:70]}")
    else:
        lines.append("Portfolio: None listed")

    # ── Proof signals ──────────────────────────────────────────────────────────
    signals = (d.get("proof_signals") or [])[:4]
    if signals:
        lines.append(f"Proof signals ({len(signals)}):")
        for sig in signals:
            detail = (sig.get("url") or sig.get("description") or "no detail")[:70]
            lines.append(f"  [{sig.get('signal_type','?')}] {sig.get('title','?')}: {detail}")
    else:
        lines.append("Proof signals: None")

    lines.append(f"CV uploaded: {'Yes' if d.get('has_cv') else 'No'}")

    # ── Authenticity flags ─────────────────────────────────────────────────────
    flags = (d.get("authenticity_flags") or [])[:5]
    if flags:
        lines.append(f"AUTH FLAGS ({len(flags)} confirmed red flags):")
        for f in flags:
            lines.append(f"  - {f[:120]}")

    # ── URL warnings ───────────────────────────────────────────────────────────
    url_warns = (d.get("url_warnings") or [])[:3]
    if url_warns:
        lines.append(f"URL WARNINGS ({len(url_warns)} dead/unreachable links):")
        for w in url_warns:
            lines.append(f"  - {w[:100]}")

    # ── JSON prefix — model MUST complete with its own computed score ───────────
    lines.append('\n--- SCORING OUTPUT ---')
    lines.append('Output ONLY valid JSON. Compute the score from the profile above.')
    lines.append('Format (strengths/risks max 2 items, max 6 words each):')
    lines.append(_JSON_PREFIX)

    return "\n".join(lines)
