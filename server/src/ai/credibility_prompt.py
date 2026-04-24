import json
import google.generativeai as genai
from src.config import settings

genai.configure(api_key=settings.gemini_api_key)
_model = genai.GenerativeModel("gemini-2.5-flash")

_SYSTEM = """You are an expert hiring analyst evaluating a freelance/professional profile for the HireCred trust-based platform.

Score the profile from 0 to 100 based on these weighted criteria:

1. PROFILE COMPLETENESS (25 pts): Bio present and substantial (>50 words), professional title set, location provided, multiple skills listed
2. SKILL vs EXPERIENCE ALIGNMENT (20 pts): Do the listed skills match the job titles and project work? Detect mismatches.
3. PORTFOLIO QUALITY (20 pts): Are portfolio descriptions detailed? Do projects have URLs or tech stacks? Vague "worked on a project" descriptions score low.
4. WRITING CLARITY (10 pts): Is the bio professional, clear, and free of generic filler phrases?
5. PROOF SIGNALS (25 pts): GitHub links (+8), portfolio links (+5), client references (+7), work screenshots (+5). No proof signals = major penalty.

Scoring guidelines:
- 0–30: Empty or near-empty profile, no proof signals, no real experience
- 31–50: Some info but missing key sections, no proof signals
- 51–70: Decent profile with skills and experience but missing proof or portfolio depth
- 71–85: Good profile with proof signals and detailed content
- 86–100: Excellent — complete, detailed, proof-backed, aligned, well-written

Return ONLY valid JSON with this exact structure, no other text:
{"credibility_score": 75, "strengths": ["specific strength 1", "specific strength 2"], "risks": ["specific risk 1"]}

Keep strengths and risks specific to this profile (2–4 items each max). Do not use generic statements."""


async def evaluate_profile(profile_data: dict) -> dict:
    """Call Gemini with structured output to return a credibility evaluation."""
    prompt = _build_prompt(profile_data)

    try:
        response = _model.generate_content(
            f"{_SYSTEM}\n\n{prompt}",
            generation_config={"temperature": 0.3, "max_output_tokens": 4096},
        )
        
        text = response.text.strip()
        # Extract JSON from response
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        
        data = json.loads(text)
        data["credibility_score"] = max(0, min(100, int(data.get("credibility_score", 0))))
        data.setdefault("strengths", [])
        data.setdefault("risks", [])
        return data
    except Exception as e:
        # Fallback scoring
        return {"credibility_score": 0, "strengths": [], "risks": ["Score could not be computed"]}


def _build_prompt(d: dict) -> str:
    lines = ["# Candidate Profile\n"]
    lines.append(f"**Name:** {d.get('owner_name', 'Unknown')}")
    lines.append(f"**Title:** {d.get('title') or 'Not specified'}")
    lines.append(f"**Location:** {d.get('location') or 'Not specified'}")
    lines.append(f"**Bio:** {d.get('bio') or 'Not provided'}\n")

    skills = d.get("skills", [])
    lines.append(f"**Skills ({len(skills)}):** {', '.join(skills) if skills else 'None listed'}\n")

    experience = d.get("experience", [])
    lines.append(f"**Experience ({len(experience)} entries):**")
    for exp in experience:
        date_range = f"{exp.get('start_date', '?')} – {'Present' if exp.get('current') else exp.get('end_date', '?')}"
        lines.append(f"  - {exp.get('title')} at {exp.get('company')} ({date_range})")
        if exp.get("description"):
            lines.append(f"    {exp['description']}")

    portfolio = d.get("portfolio", [])
    lines.append(f"\n**Portfolio ({len(portfolio)} items):**")
    for item in portfolio:
        lines.append(f"  - {item.get('title')}: {item.get('description') or 'No description'}")
        if item.get("url"):
            lines.append(f"    URL: {item['url']}")
        if item.get("tech_stack"):
            lines.append(f"    Tech: {', '.join(item['tech_stack'])}")

    proof_signals = d.get("proof_signals", [])
    lines.append(f"\n**Proof Signals ({len(proof_signals)}):**")
    for sig in proof_signals:
        detail = sig.get("url") or sig.get("description") or "No details"
        lines.append(f"  - [{sig.get('signal_type')}] {sig.get('title')}: {detail}")

    return "\n".join(lines)
