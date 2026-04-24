import asyncio
import json
import google.generativeai as genai
from src.config import settings

genai.configure(api_key=settings.gemini_api_key)
_model = genai.GenerativeModel("gemini-2.5-flash")

_SYSTEM = """You are HireCred's trust evaluator. Analyze the candidate profile below and score their professional credibility from 0 to 100.

Scoring rubric (total 100 points):
- Profile completeness — bio present + specific, skills ≥3, experience ≥1, portfolio ≥1: 25 pts
- Skill–experience alignment — claimed skills appear in experience/portfolio descriptions: 25 pts
- Portfolio quality — detailed descriptions, live links present, varied projects: 20 pts
- Writing clarity — bio is professional and specific, not generic filler: 15 pts
- Proof signals — GitHub/project link +8, screenshot +5, client reference +7 (cap 15): 15 pts

Be concrete. Strengths and risks should reference actual profile content, not generic advice.

IMPORTANT: Return ONLY valid JSON with this exact structure, no other text:
{
  "credibility_score": 75,
  "strengths": ["strength1", "strength2"],
  "risks": ["risk1", "risk2"]
}"""


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


async def evaluate_profile(profile_data: dict) -> dict:
    """Call Gemini with structured output to return a credibility evaluation."""
    prompt = _build_prompt(profile_data)
    print(f"\nDebug: Built prompt ({len(prompt)} chars):")
    print(prompt[:200])

    try:
        print("\nDebug: Calling generate_content...")
        response = _model.generate_content(
            f"{_SYSTEM}\n\n{prompt}",
            generation_config={"temperature": 0.3, "max_output_tokens": 2048},
        )
        
        text = response.text.strip()
        print(f"Debug: Got response ({len(text)} chars)")
        print(f"Debug: First 300 chars: {text[:300]}")
        
        # Extract JSON from response
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
            print("Debug: Extracted from ```json block")
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
            print("Debug: Extracted from ``` block")
        else:
            print("Debug: No code block found, trying direct JSON parse")
        
        print(f"Debug: After extraction ({len(text)} chars): {text[:200]}")
        
        data = json.loads(text)
        print(f"Debug: Successfully parsed JSON: {list(data.keys())}")
        
        data["credibility_score"] = max(0, min(100, int(data.get("credibility_score", 0))))
        data.setdefault("strengths", [])
        data.setdefault("risks", [])
        return data
    except Exception as e:
        print(f"Debug: Exception occurred: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        # Fallback scoring
        return {"credibility_score": 0, "strengths": [], "risks": ["Score could not be computed"]}


async def main():
    profile_data = {
        "owner_name": "Test Dev",
        "title": "Engineer",
        "bio": "Building secure web products.",
        "skills": ["React", "TypeScript", "FastAPI"],
        "experience": [
            {
                "title": "Engineer",
                "company": "Corp",
                "start_date": "2023",
                "current": True,
                "description": "Built features",
            }
        ],
        "portfolio": [
            {
                "title": "App",
                "description": "Platform",
                "url": "https://example.com",
                "tech_stack": ["React"],
            }
        ],
        "proof_signals": [
            {"signal_type": "github", "title": "GitHub", "url": "https://github.com/test"}
        ],
    }
    
    print("Testing evaluate_profile with debugging...")
    result = await evaluate_profile(profile_data)
    print(f"\nFinal result: {result}")


asyncio.run(main())
