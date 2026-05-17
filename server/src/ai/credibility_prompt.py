"""
Profile credibility scoring prompt — optimised for fast local inference.
Kept compact to stay well within num_ctx=2048.
"""
import logging
from datetime import datetime, timezone
from src.ai.ollama_client import call_ollama, extract_json

logger = logging.getLogger(__name__)

# Compact system prompt — ~120 tokens vs the previous ~900
_SYSTEM = """Score this candidate 0-100. Return ONLY the JSON below, no other text.
Criteria: completeness(18)+skill-experience match(22)+portfolio(22)+writing(8)+proof signals(18)+CV(12).
AUTH FLAGS=confirmed red flags, penalise each. URL WARNS=dead links, deduct. No CV=CV score 0.
Sci-fi content/fictional dates(3000+)/joke skills/impossible claims → score≤15. Two fake signals → score≤10+fraud_flags.
Strengths and risks: max 6 words each, 2 items max.
{"credibility_score":75,"strengths":["reason1","reason2"],"risks":["risk1"],"fraud_flags":[]}"""


async def evaluate_profile(profile_data: dict) -> dict:
    """Call Ollama to score the profile. Returns parsed score dict."""
    prompt = _build_prompt(profile_data)
    try:
        text = await call_ollama(prompt, num_predict=250)
        data = _safe_extract_json(text)
        data["credibility_score"] = max(0, min(100, int(data.get("credibility_score", 0))))
        # Strip empty/whitespace strings the model occasionally emits
        data["strengths"] = [s for s in data.get("strengths", []) if isinstance(s, str) and s.strip()]
        data["risks"] = [r for r in data.get("risks", []) if isinstance(r, str) and r.strip()]
        data["fraud_flags"] = [f for f in data.get("fraud_flags", []) if isinstance(f, str) and f.strip()]
        return data
    except Exception as exc:
        logger.warning("Ollama scoring failed [%s]: %s", type(exc).__name__, exc)
        raise RuntimeError(f"Ollama scoring failed [{type(exc).__name__}]: {exc}") from exc


def _safe_extract_json(text: str) -> dict:
    try:
        return extract_json(text)
    except Exception:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            import json
            try:
                return json.loads(text[start:end])
            except Exception:
                pass
        raise ValueError(f"Could not parse JSON: {text[:150]!r}")


def _build_prompt(d: dict) -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m")
    lines = [_SYSTEM, f"\nDate: {today}"]

    # ── Core profile ───────────────────────────────────────────────────────────
    lines.append(f"Title: {(d.get('title') or 'None')[:60]}")
    lines.append(f"Location: {(d.get('location') or 'None')[:40]}")
    bio = (d.get("bio") or "").strip()
    if bio:
        lines.append(f"Bio: {bio[:200]}")

    skills = d.get("skills") or []
    if skills:
        lines.append(f"Skills: {', '.join(skills[:15])}")

    # ── Experience (cap at 3 entries) ──────────────────────────────────────────
    experience = (d.get("experience") or [])[:3]
    if experience:
        lines.append("Experience:")
        for exp in experience:
            dates = f"{exp.get('start_date','?')}-{'now' if exp.get('current') else (exp.get('end_date') or '?')}"
            lines.append(f"  {exp.get('title','?')} @ {exp.get('company','?')} ({dates})")
            desc = (exp.get("description") or "").strip()
            if desc:
                lines.append(f"    {desc[:120]}")

    # ── Portfolio (cap at 3 items) ─────────────────────────────────────────────
    portfolio = (d.get("portfolio") or [])[:3]
    if portfolio:
        lines.append("Portfolio:")
        for item in portfolio:
            lines.append(f"  {item.get('title','?')}: {(item.get('description') or '')[:100]}")
            if item.get("url"):
                lines.append(f"    URL: {item['url'][:60]}")

    # ── Proof signals (cap at 4) ───────────────────────────────────────────────
    signals = (d.get("proof_signals") or [])[:4]
    if signals:
        lines.append(f"Proof signals ({len(signals)}):")
        for sig in signals:
            detail = (sig.get("url") or sig.get("description") or "")[:60]
            lines.append(f"  [{sig.get('signal_type','?')}] {sig.get('title','?')}: {detail}")

    # ── CV ─────────────────────────────────────────────────────────────────────
    lines.append(f"CV uploaded: {'Yes' if d.get('has_cv') else 'No'}")

    # ── Authenticity flags (cap at 5 most important) ───────────────────────────
    flags = (d.get("authenticity_flags") or [])[:5]
    if flags:
        lines.append("AUTH FLAGS:")
        for f in flags:
            lines.append(f"  [FLAG] {f[:120]}")

    # ── URL warnings (cap at 3) ────────────────────────────────────────────────
    warnings = (d.get("url_warnings") or [])[:3]
    if warnings:
        lines.append("URL WARNINGS:")
        for w in warnings:
            lines.append(f"  [WARN] {w[:100]}")

    return "\n".join(lines)
