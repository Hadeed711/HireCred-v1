import logging
from src.ai.ollama_client import call_ollama, extract_json

logger = logging.getLogger(__name__)

_SYSTEM = """You are a job search query parser for a hiring platform.
Parse the user's natural language hiring query and extract structured intent.

Determine the search_tier based on the query:
- "profession": query is about a specific job title/profession (doctor, lawyer, nurse, chef, teacher, dentist, architect, pilot, psychologist, accountant, pharmacist, plumber, electrician, engineer, developer, designer, etc.)
- "skill": query is about specific technical or professional skills (React, Python, data science, UI/UX, accounting software, etc.)
- "domain": query is about a topic, field, or domain concept that is NOT a specific person role (foods with iron, renewable energy, sustainable fashion, blockchain technology, etc.)

For profession queries, extract the profession word(s) into profession_keywords.
For skill queries, extract required_skills generously (include synonyms and related technologies).
For domain queries, required_skills can be empty.

For min_credibility_score:
- "high credibility", "high trust", "highly trusted", "top credibility", "very reliable", "most trusted" -> 70
- "moderate credibility", "average trust", "medium trust" -> 40
- no credibility qualifier mentioned -> 0

Return ONLY valid JSON with this exact structure, no other text:
{
  "search_tier": "skill",
  "profession_keywords": [],
  "required_skills": ["skill1", "skill2"],
  "trust_keywords": ["reliable", "verified"],
  "experience_level": null,
  "trust_priority": false,
  "min_credibility_score": 0
}

experience_level must be "junior", "mid", "senior", or null.
Seniority words (fresher, fresh graduate, entry-level, intern, trainee, beginner,
junior, mid-level, senior, lead, principal) describe experience_level ONLY —
NEVER put them in required_skills or profession_keywords.
"fresher", "intern", "trainee", "graduate", "entry-level", "beginner" -> experience_level "junior"."""


async def parse_search_query(query: str) -> dict:
    """Parse a natural language search query into structured intent using Ollama."""
    prompt = f"{_SYSTEM}\n\nSearch query: {query[:500]}"
    try:
        text = await call_ollama(prompt, num_predict=256)
        data = extract_json(text)
        data["required_skills"] = [s.lower().strip() for s in data.get("required_skills", [])]
        data["profession_keywords"] = [p.lower().strip() for p in data.get("profession_keywords", [])]
        data.setdefault("search_tier", "skill")
        data.setdefault("trust_keywords", [])
        data.setdefault("trust_priority", False)
        data.setdefault("experience_level", None)
        data.setdefault("min_credibility_score", 0)
        if data["search_tier"] not in ("profession", "skill", "domain"):
            data["search_tier"] = "skill"
        return data
    except Exception as exc:
        logger.warning("Ollama search parsing failed (%s), using keyword fallback", exc)
        return {
            "search_tier": "skill",
            "profession_keywords": [],
            "required_skills": [],
            "trust_keywords": [],
            "trust_priority": False,
            "experience_level": None,
            "min_credibility_score": 0,
        }
