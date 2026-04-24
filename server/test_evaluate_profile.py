import asyncio
import json
from src.ai.credibility_prompt import evaluate_profile

async def test():
    profile_data = {
        "owner_name": "Test Dev",
        "title": "Engineer",
        "bio": "Building secure web products.",
        "skills": ["React", "TypeScript", "FastAPI"],
        "experience": [
            {
                "title": "Engineer",
                "company": "Corp",
                "start_date": "2023",
                "current": True,
                "description": "Built features",
            }
        ],
        "portfolio": [
            {
                "title": "App",
                "description": "Platform",
                "url": "https://example.com",
                "tech_stack": ["React"],
            }
        ],
        "proof_signals": [
            {"signal_type": "github", "title": "GitHub", "url": "https://github.com/test"}
        ],
    }
    
    print("Testing evaluate_profile...")
    result = await evaluate_profile(profile_data)
    print(f"Result: {result}")
    print(f"Credibility score: {result.get('credibility_score')}")
    print(f"Strengths: {result.get('strengths')}")

asyncio.run(test())
