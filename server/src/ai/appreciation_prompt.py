import logging
from src.ai.ollama_client import call_ollama, extract_json

logger = logging.getLogger(__name__)

_SYSTEM = """You are analyzing a client's written feedback about a freelancer.
Extract and rate the following three dimensions from 0.0 to 10.0 based only on what is clearly stated in the text.
Do not invent information not present. If a dimension is not mentioned at all, give a neutral score of 5.0.

Dimensions:
- skill_rating: technical competence, quality of delivered work
- communication_rating: responsiveness, clarity, keeping the client informed
- reliability_rating: meeting deadlines, delivering what was promised, dependability

Also write a single neutral sentence summarising what the feedback says.

Return ONLY valid JSON with this exact structure, no other text:
{"skill_rating": 7.5, "communication_rating": 8.0, "reliability_rating": 7.5, "summary": "One sentence summary."}"""


async def analyze_feedback(raw_feedback: str) -> dict:
    """Call Ollama to convert raw feedback text into structured ratings."""
    prompt = f"{_SYSTEM}\n\nClient feedback:\n\n{raw_feedback[:1500]}"
    try:
        text = await call_ollama(prompt, num_predict=256)
        data = extract_json(text)
        for key in ("skill_rating", "communication_rating", "reliability_rating"):
            data[key] = max(0.0, min(10.0, float(data.get(key, 5.0))))
        data.setdefault("summary", "Feedback received.")
        return data
    except Exception as exc:
        logger.warning("Ollama appreciation analysis failed: %s", exc)
        return {
            "skill_rating": 5.0,
            "communication_rating": 5.0,
            "reliability_rating": 5.0,
            "summary": "Feedback received.",
        }
