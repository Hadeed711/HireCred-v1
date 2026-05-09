import logging
from src.ai.ollama_client import call_ollama, extract_json

logger = logging.getLogger(__name__)

_SYSTEM = """You are doing a quick check on a CV/resume snippet.

From the text below, extract:
1. extracted_skills: up to 8 skills or tools mentioned (empty list if none found)
2. experience_summary: one short sentence describing the person's background (e.g. "3 years in software development")
3. is_authentic: true unless the text is clearly a blank template (contains "Your Name Here", "Lorem ipsum", "Insert experience here", or is fewer than 20 real words)

Return ONLY valid JSON, no other text:
{"extracted_skills": [], "experience_summary": "", "is_authentic": true}"""


async def analyze_cv(cv_text: str) -> dict:
    """Quick Ollama check on CV snippet — not a deep analysis."""
    # Send only first 1500 chars — one page is enough
    snippet = cv_text[:1500].strip()
    prompt = f"{_SYSTEM}\n\nCV snippet:\n{snippet}"
    try:
        text = await call_ollama(prompt, num_predict=200)
        data = extract_json(text)
        data["extracted_skills"] = [s.strip() for s in data.get("extracted_skills", []) if s.strip()][:8]
        data.setdefault("experience_summary", "")
        data.setdefault("is_authentic", True)
        data["rejection_reason"] = "" if data["is_authentic"] else "CV appears to be a blank template."
        return data
    except Exception as exc:
        logger.warning("CV analysis failed: %s — treating as authentic", exc)
        # Don't block upload if AI fails — just store empty analysis
        return {"extracted_skills": [], "experience_summary": "", "is_authentic": True, "rejection_reason": ""}
