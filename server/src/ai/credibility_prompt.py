import logging
from datetime import datetime, timezone
from src.ai.ollama_client import call_ollama, extract_json

logger = logging.getLogger(__name__)

_SYSTEM = """You are an expert hiring analyst evaluating a professional profile for the HireCred trust-based platform.

Score the profile from 0 to 100 based on these weighted criteria:

1. PROFILE COMPLETENESS (25 pts): Bio present and substantial (>50 words), professional title set, location provided, multiple skills listed
2. SKILL vs EXPERIENCE ALIGNMENT (20 pts): Do the listed skills match the job titles and project work? Detect mismatches.
3. PORTFOLIO QUALITY (20 pts): Are portfolio descriptions detailed? Do projects have URLs or tech stacks? Vague descriptions score low.
4. WRITING CLARITY (10 pts): Is the bio professional, clear, and free of generic filler phrases?
5. PROOF SIGNALS (15 pts): GitHub links (+5), portfolio links (+3), client references (+4), work screenshots (+3). No proof signals = major penalty.
6. CV QUALITY (10 pts): If a CV is attached, does it show real roles, dates, and skills? Blank or template CVs score 0 here.

Scoring guidelines:
- 0–30: Empty or near-empty profile, no proof signals, no real experience
- 31–50: Some info but missing key sections, no proof signals
- 51–70: Decent profile with skills and experience but missing proof or portfolio depth
- 71–85: Good profile with proof signals and detailed content
- 86–100: Excellent — complete, detailed, proof-backed, aligned, well-written, strong CV

IMPORTANT DATE RULE: The profile will include a "Today's date" field. Use that date as the reference for "now". Any experience date on or before that date is in the past. Only flag start_date values that are strictly after today's date.

Return ONLY valid JSON with this exact structure, no other text:
{"credibility_score": 75, "strengths": ["specific strength 1", "specific strength 2"], "risks": ["specific risk 1"]}

Keep strengths and risks specific to this profile (2–4 items each max). Do not use generic statements."""


async def evaluate_profile(profile_data: dict) -> dict:
    """Call Ollama to return a credibility evaluation for the profile."""
    prompt = f"{_SYSTEM}\n\n{_build_prompt(profile_data)}"
    try:
        text = await call_ollama(prompt, num_predict=512)
        data = extract_json(text)
        data["credibility_score"] = max(0, min(100, int(data.get("credibility_score", 0))))
        data.setdefault("strengths", [])
        data.setdefault("risks", [])
        return data
    except Exception as exc:
        logger.warning("Ollama credibility scoring failed: %s", exc)
        raise RuntimeError(f"Ollama credibility scoring failed: {exc}") from exc


def _build_prompt(d: dict) -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m")
    lines = ["# Candidate Profile\n"]
    lines.append(f"Today's date: {today}")
    lines.append(f"Name: {d.get('owner_name', 'Unknown')}")
    lines.append(f"Title: {d.get('title') or 'Not specified'}")
    lines.append(f"Location: {d.get('location') or 'Not specified'}")
    lines.append(f"Bio: {d.get('bio') or 'Not provided'}\n")

    skills = d.get("skills", [])
    lines.append(f"Skills ({len(skills)}): {', '.join(skills) if skills else 'None listed'}\n")

    experience = d.get("experience", [])
    lines.append(f"Experience ({len(experience)} entries):")
    for exp in experience:
        date_range = f"{exp.get('start_date', '?')} - {'Present' if exp.get('current') else exp.get('end_date', '?')}"
        lines.append(f"  - {exp.get('title')} at {exp.get('company')} ({date_range})")
        if exp.get("description"):
            lines.append(f"    {exp['description'][:200]}")

    portfolio = d.get("portfolio", [])
    lines.append(f"\nPortfolio ({len(portfolio)} items):")
    for item in portfolio:
        lines.append(f"  - {item.get('title')}: {(item.get('description') or 'No description')[:150]}")
        if item.get("url"):
            lines.append(f"    URL: {item['url']}")
        if item.get("tech_stack"):
            lines.append(f"    Tech: {', '.join(item['tech_stack'])}")

    proof_signals = d.get("proof_signals", [])
    lines.append(f"\nProof Signals ({len(proof_signals)}):")
    for sig in proof_signals:
        detail = sig.get("url") or sig.get("description") or "No details"
        lines.append(f"  - [{sig.get('signal_type')}] {sig.get('title')}: {detail[:100]}")

    cv_analysis = d.get("cv_analysis")
    if cv_analysis:
        lines.append(f"\nCV Analysis:")
        lines.append(f"  Extracted skills: {', '.join(cv_analysis.get('extracted_skills', []))}")
        lines.append(f"  Experience summary: {cv_analysis.get('experience_summary', 'N/A')[:200]}")
        lines.append(f"  CV authentic: {cv_analysis.get('is_authentic', True)}")
    else:
        lines.append("\nCV: Not uploaded")

    return "\n".join(lines)
