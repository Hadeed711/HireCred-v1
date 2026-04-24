import json
import google.generativeai as genai
from src.config import settings

genai.configure(api_key=settings.gemini_api_key)
_model = genai.GenerativeModel("gemini-2.5-flash")

_SYSTEM = """You are analyzing a set of client appreciations for a single freelancer to detect fake or manipulated reviews.

Look for these specific patterns:
- Generic, templated language (e.g. "great work, highly recommend", "would hire again", "amazing freelancer")
- Suspiciously perfect scores (all or nearly all ratings at 9.0–10.0 with no nuance or specifics)
- Reviews that are too short (under 20 words) to contain real project information
- Uniform writing style across multiple reviews (same sentence structure, similar phrasing)
- Lack of specific project details (no mention of what was built, timeline, or technical specifics)

Only flag real concerns. A small number of short positive reviews from a new freelancer is normal.
If you find no suspicious patterns, return fraud_risk "low" with an empty flags list.

IMPORTANT: Return ONLY valid JSON with this exact structure, no other text:
{
  "fraud_risk": "low",
  "flags": []
}"""


async def analyze_appreciations(appreciations: list[dict]) -> dict:
    """Call Gemini to detect fake or manipulated review patterns across appreciations."""
    if not appreciations:
        return {"fraud_risk": "low", "flags": []}

    feedback_text = "\n\n".join(
        f"Review {i + 1} "
        f"(skill={a['skill_rating']:.1f}, comm={a['communication_rating']:.1f}, rel={a['reliability_rating']:.1f}):\n"
        f"{a['raw_feedback']}"
        for i, a in enumerate(appreciations)
    )

    try:
        prompt = (
            f"{_SYSTEM}\n\n"
            f"Analyze these {len(appreciations)} review(s) for signs of fake or manipulated feedback:\n\n"
            f"{feedback_text}"
        )
        response = _model.generate_content(
            prompt,
            generation_config={"temperature": 0.3, "max_output_tokens": 2048},
        )
        
        text = response.text.strip()
        # Extract JSON from response
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        
        data = json.loads(text)
        if data.get("fraud_risk") not in ("low", "medium", "high"):
            data["fraud_risk"] = "low"
        data["flags"] = data.get("flags") or []
        return data
    except Exception as e:
        # Fallback on error
        return {"fraud_risk": "low", "flags": []}
