import json
import google.generativeai as genai
from src.config import settings

genai.configure(api_key=settings.gemini_api_key)
_model = genai.GenerativeModel("gemini-2.5-flash")

_SYSTEM = """You are analyzing a client's written feedback about a freelancer.
Extract and rate the following three dimensions from 0.0 to 10.0 based only on what is clearly implied or stated in the text.
Do not invent information that is not present. If a dimension is not mentioned at all, give a neutral score of 5.0.

Dimensions:
- skill_rating: technical competence, quality of delivered work
- communication_rating: responsiveness, clarity, keeping the client informed
- reliability_rating: meeting deadlines, delivering what was promised, dependability

Also write a single neutral sentence that summarises what the feedback says.

IMPORTANT: Return ONLY valid JSON with this exact structure, no other text:
{
  "skill_rating": 7.5,
  "communication_rating": 8.0,
  "reliability_rating": 7.5,
  "summary": "One sentence summary of the feedback."
}"""


async def analyze_feedback(raw_feedback: str) -> dict:
    """Call Gemini with structured output to convert raw feedback text into ratings."""
    try:
        response = _model.generate_content(
            f"{_SYSTEM}\n\nClient feedback:\n\n{raw_feedback}",
            generation_config={"temperature": 0.3, "max_output_tokens": 2048},
        )
        
        text = response.text.strip()
        # Extract JSON from response
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        
        data = json.loads(text)
        # Clamp values to valid range
        for key in ("skill_rating", "communication_rating", "reliability_rating"):
            data[key] = max(0.0, min(10.0, float(data.get(key, 5.0))))
        data.setdefault("summary", "Feedback received.")
        return data
    except Exception as e:
        # Fallback on error
        return {
            "skill_rating": 5.0,
            "communication_rating": 5.0,
            "reliability_rating": 5.0,
            "summary": "Feedback received.",
        }
