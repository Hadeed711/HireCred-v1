import json
import google.generativeai as genai
from src.config import settings

genai.configure(api_key=settings.gemini_api_key)
_model = genai.GenerativeModel("gemini-2.5-flash")

_SYSTEM = """You are a job search query parser for a hiring platform.
Parse the user's natural language hiring query and extract structured intent from it.
Be generous in skill extraction — include synonyms and related technologies.
For example: "React developer" → also include "JavaScript", "frontend".
If no specific skills are mentioned, return an empty list.

For min_credibility_score, use these rules:
- "high credibility", "high trust", "highly trusted", "top credibility", "very reliable", "most trusted" → 70
- "moderate credibility", "average trust", "medium trust" → 40
- "low credibility", "low trust" or no credibility qualifier mentioned → 0

IMPORTANT: Return ONLY valid JSON with this exact structure, no other text:
{
  "required_skills": ["skill1", "skill2"],
  "trust_keywords": ["reliable", "verified"],
  "experience_level": "junior" | "mid" | "senior" | null,
  "trust_priority": true/false,
  "min_credibility_score": 0
}"""


async def parse_search_query(query: str) -> dict:
    """Parse a natural language search query into structured intent using Gemini."""
    try:
        response = _model.generate_content(
            f"{_SYSTEM}\n\nSearch query: {query}",
            generation_config={"temperature": 0.3, "max_output_tokens": 2048},
        )
        
        text = response.text.strip()
        # Try to extract JSON from response
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        
        data = json.loads(text)
        # Normalise skill names to lowercase for case-insensitive matching
        data["required_skills"] = [s.lower().strip() for s in data.get("required_skills", [])]
        data.setdefault("trust_keywords", [])
        data.setdefault("trust_priority", False)
        data.setdefault("experience_level", None)
        data.setdefault("min_credibility_score", 0)
        return data
    except Exception as e:
        return {"required_skills": [], "trust_keywords": [], "trust_priority": False, "experience_level": None, "min_credibility_score": 0}
