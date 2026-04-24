import asyncio
import google.generativeai as genai
from src.config import settings

genai.configure(api_key=settings.gemini_api_key)
_model = genai.GenerativeModel("gemini-2.5-flash")

_SYSTEM = """Score this profile from 0-100.
Return ONLY JSON:
{"credibility_score": 75, "strengths": [], "risks": []}"""

async def test():
    response = _model.generate_content(
        contents=[
            {
                "role": "user",
                "parts": [{"text": f"{_SYSTEM}\n\nProfile: Test dev with React skills"}],
            }
        ],
        generation_config={"temperature": 0.3, "max_output_tokens": 2048},
    )
    
    text = response.text.strip()
    print("Raw response:")
    print(text[:500])

asyncio.run(test())
