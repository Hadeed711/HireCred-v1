import asyncio
import google.generativeai as genai
from src.config import settings

genai.configure(api_key=settings.gemini_api_key)
_model = genai.GenerativeModel("gemini-2.5-flash")

_SYSTEM = """Score from 0-100. Return ONLY JSON:
{"credibility_score": 75, "strengths": [], "risks": []}"""

async def test():
    response = _model.generate_content(
        f"{_SYSTEM}\n\nTest profile with React, TypeScript, and FastAPI skills. Experience at Corp building features. Portfolio with app.",
        generation_config={"temperature": 0.3, "max_output_tokens": 2048},
    )
    
    print(f"Response object type: {type(response)}")
    print(f"Response text length: {len(response.text)}")
    print(f"Response text:\n{response.text}\n")
    
    # Check if response has multiple parts
    if hasattr(response, 'candidates'):
        print(f"Candidates: {len(response.candidates)}")
        for i, candidate in enumerate(response.candidates):
            print(f"  Candidate {i}: {candidate.content.parts if hasattr(candidate, 'content') else 'N/A'}")

asyncio.run(test())
