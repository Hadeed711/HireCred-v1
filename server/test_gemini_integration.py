import asyncio
from src.ai.search_prompt import parse_search_query
from src.ai.credibility_prompt import evaluate_profile
from src.ai.appreciation_prompt import analyze_feedback
from src.ai.fraud_prompt import analyze_appreciations


async def main():
    print("🔄 Testing Gemini API Integration...\n")
    
    # Test 1: Search query parsing
    print("1️⃣  Testing Search Query Parser...")
    try:
        parsed = await parse_search_query("Looking for a reliable React developer")
        assert parsed.get("required_skills"), "No skills extracted"
        print(f"   ✅ Skills: {parsed.get('required_skills')}")
        print(f"   ✅ Trust priority: {parsed.get('trust_priority')}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

    # Test 2: Profile credibility scoring
    print("\n2️⃣  Testing Profile Credibility Scoring...")
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
    try:
        score = await evaluate_profile(profile_data)
        assert score.get("credibility_score", 0) > 0, f"Score is 0: {score}"
        print(f"   ✅ Score: {score.get('credibility_score')}/100")
        print(f"   ✅ Strengths: {len(score.get('strengths', []))} items")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

    # Test 3: Appreciation analysis
    print("\n3️⃣  Testing Appreciation Feedback Analysis...")
    try:
        appr = await analyze_feedback("Delivered on time with clear communication.")
        assert appr.get("skill_rating", 0) > 0 or appr.get("communication_rating", 0) > 0
        print(f"   ✅ Skill: {appr.get('skill_rating')}/10")
        print(f"   ✅ Communication: {appr.get('communication_rating')}/10")
        print(f"   ✅ Reliability: {appr.get('reliability_rating')}/10")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

    # Test 4: Fraud detection
    print("\n4️⃣  Testing Fraud Detection...")
    try:
        appreciations = [
            {
                "raw_feedback": "Great work, highly recommend!",
                "skill_rating": 10.0,
                "communication_rating": 10.0,
                "reliability_rating": 10.0,
            },
            {
                "raw_feedback": "Amazing, would hire again!",
                "skill_rating": 10.0,
                "communication_rating": 10.0,
                "reliability_rating": 10.0,
            },
        ]
        fraud = await analyze_appreciations(appreciations)
        assert fraud.get("fraud_risk") in ["low", "medium", "high"]
        print(f"   ✅ Fraud risk: {fraud.get('fraud_risk')}")
        print(f"   ✅ Flags: {len(fraud.get('flags', []))} issues")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

    print("\n✅ All Gemini API tests PASSED!")
    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    import sys

    sys.exit(0 if success else 1)
