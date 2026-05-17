"""
CV analysis via Ollama — uses pre-extracted pdfplumber text and section data.
Provides rich structured output: skills, section headings, authenticity, match signals.
"""
import logging
from src.ai.ollama_client import call_ollama, extract_json

logger = logging.getLogger(__name__)

_SYSTEM = """You are analysing a CV/resume that has already been extracted from a PDF.

From the provided text and detected section headings, extract:
1. extracted_skills: list of up to 10 specific skills or technologies mentioned (empty list if none)
2. experience_summary: one concise sentence describing the person's background (e.g. "5 years in backend engineering across fintech and SaaS")
3. cv_title: the candidate's apparent job title/role from the CV (empty string if not found)
4. is_authentic: false ONLY if the text is clearly a blank template ("Your Name Here", "Lorem ipsum", "Insert experience here") OR fewer than 30 real words
5. rejection_reason: empty string if authentic; otherwise a short human-readable reason

Return ONLY valid JSON, no other text:
{"extracted_skills": [], "experience_summary": "", "cv_title": "", "is_authentic": true, "rejection_reason": ""}"""


async def analyze_cv(cv_text: str, sections: list[str] | None = None) -> dict:
    """
    Analyse CV text using Ollama. Uses first 2500 chars of text plus section list.
    Falls back gracefully if Ollama is unavailable.
    """
    snippet = cv_text[:2500].strip()
    section_hint = ""
    if sections:
        section_hint = f"\nDetected section headings: {', '.join(sections)}"

    prompt = f"{_SYSTEM}\n\nCV text:\n{snippet}{section_hint}"
    try:
        text = await call_ollama(prompt, num_predict=250)
        data = extract_json(text)
        data["extracted_skills"] = [s.strip() for s in data.get("extracted_skills", []) if s.strip()][:10]
        data.setdefault("experience_summary", "")
        data.setdefault("cv_title", "")
        data.setdefault("is_authentic", True)
        data.setdefault("rejection_reason", "")
        if not data["is_authentic"] and not data["rejection_reason"]:
            data["rejection_reason"] = "CV appears to be a blank template."
        return data
    except Exception as exc:
        logger.warning("CV analysis failed: %s — treating as authentic", exc)
        return {
            "extracted_skills": [],
            "experience_summary": "",
            "cv_title": "",
            "is_authentic": True,
            "rejection_reason": "",
        }
