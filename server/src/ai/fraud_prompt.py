import logging
from src.ai.ollama_client import call_ollama, extract_json

logger = logging.getLogger(__name__)

_SYSTEM = """You are analyzing a set of client appreciations for a single freelancer to detect fake or manipulated reviews.

Look for these specific patterns:
- Generic, templated language (e.g. "great work, highly recommend", "would hire again")
- Suspiciously perfect scores (all ratings at 9.0-10.0 with no nuance or specifics)
- Reviews under 20 words that contain no real project information
- Uniform writing style across multiple reviews (same sentence structure, similar phrasing)
- Lack of specific project details (no mention of what was built, timeline, or technical specifics)

Only flag real concerns. A small number of short positive reviews from a new freelancer is normal.
If you find no suspicious patterns, return fraud_risk "low" with an empty flags list.

Return ONLY valid JSON with this exact structure, no other text:
{"fraud_risk": "low", "flags": []}"""


async def analyze_appreciations(appreciations: list[dict]) -> dict:
    """Call Ollama to detect fake or manipulated review patterns across appreciations."""
    if not appreciations:
        return {"fraud_risk": "low", "flags": []}

    feedback_text = "\n\n".join(
        f"Review {i + 1} "
        f"(skill={a['skill_rating']:.1f}, comm={a['communication_rating']:.1f}, rel={a['reliability_rating']:.1f}):\n"
        f"{a['raw_feedback'][:300]}"
        for i, a in enumerate(appreciations[:10])  # cap at 10 to stay within ctx
    )

    prompt = (
        f"{_SYSTEM}\n\n"
        f"Analyze these {len(appreciations)} review(s) for signs of fake or manipulated feedback:\n\n"
        f"{feedback_text}"
    )
    try:
        text = await call_ollama(prompt, num_predict=256)
        data = extract_json(text)
        if data.get("fraud_risk") not in ("low", "medium", "high"):
            data["fraud_risk"] = "low"
        data["flags"] = data.get("flags") or []
        return data
    except Exception as exc:
        logger.warning("Ollama fraud analysis failed: %s", exc)
        return {"fraud_risk": "low", "flags": []}
