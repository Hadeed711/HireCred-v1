import uuid
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from src.models.user import User, UserRole
from src.models.profile import Profile
from src.models.credibility_score import CredibilityScore
from src.models.appreciation import Appreciation
from src.ai.search_prompt import parse_search_query

logger = logging.getLogger(__name__)

_STOP_WORDS = {
    'a','an','the','for','with','who','is','are','and','or','but','in','on','at','to','of',
    'looking','need','want','hire','find','someone','i','we','our','my','good','great',
    'please','help','can','could','would','should','have','has','had','do','does','did',
    'get','got','any','some','this','that','these','those',
}


def _simple_parse_fallback(query: str) -> dict:
    """Keyword-based query parser used when the AI is unavailable."""
    words = [w.strip('.,!?()') for w in query.lower().split()]
    # Multi-word skill phrases
    text = query.lower()
    phrases = []
    for phrase in ['full stack', 'full-stack', 'machine learning', 'data science',
                   'ui ux', 'ui/ux', 'mobile app', 'web development', 'back end',
                   'front end', 'back-end', 'front-end', 'devops', 'cloud computing']:
        if phrase.replace('-', ' ') in text or phrase in text:
            phrases.append(phrase.replace('-', ' '))

    single_words = [w for w in words if w not in _STOP_WORDS and len(w) > 2]
    skills = phrases + [w for w in single_words if w not in ' '.join(phrases)]

    trust_words = [w for w in words if w in {
        'reliable', 'trusted', 'verified', 'experienced', 'senior', 'expert',
        'honest', 'professional', 'certified', 'proven',
    }]

    exp_level = None
    if 'senior' in words or 'sr' in words:
        exp_level = 'senior'
    elif 'junior' in words or 'jr' in words or 'entry' in words:
        exp_level = 'junior'
    elif 'mid' in words or 'middle' in words or 'intermediate' in words:
        exp_level = 'mid'

    text_lower = query.lower()
    if any(p in text_lower for p in ['high credibility', 'high trust', 'highly trusted', 'top credibility', 'most trusted']):
        min_score = 70
    elif any(p in text_lower for p in ['moderate credibility', 'average trust', 'medium trust']):
        min_score = 40
    else:
        min_score = 0

    return {
        "required_skills": skills[:8],
        "trust_keywords": trust_words,
        "trust_priority": bool(trust_words),
        "experience_level": exp_level,
        "min_credibility_score": min_score,
    }


async def search_candidates(query: str, db: AsyncSession) -> dict:
    """Parse query with AI (fallback to keywords), query DB, rank results."""

    # ── Step 1: Parse query ──────────────────────────────────────────────────
    try:
        parsed = await parse_search_query(query)
    except Exception:
        logger.warning("AI search parsing failed, using keyword fallback")
        parsed = _simple_parse_fallback(query)

    required_skills: list[str] = parsed["required_skills"]
    trust_priority: bool = parsed["trust_priority"]
    min_credibility_score: int = int(parsed.get("min_credibility_score", 0))

    # ── Step 2: Load all candidates with profiles ────────────────────────────
    stmt = (
        select(User, Profile, CredibilityScore)
        .join(Profile, Profile.user_id == User.id)
        .outerjoin(CredibilityScore, CredibilityScore.user_id == User.id)
        .where(User.role == UserRole.candidate)
    )
    rows = (await db.execute(stmt)).all()

    if not rows:
        return {"parsed": parsed, "results": []}

    # ── Step 3a: Minimum credibility filter ─────────────────────────────────
    if min_credibility_score > 0:
        rows = [
            r for r in rows
            if (r.CredibilityScore and r.CredibilityScore.score >= min_credibility_score)
        ]

    # ── Step 3b: Skill overlap filter ────────────────────────────────────────
    def skill_overlap(candidate_skills: list[str]) -> set[str]:
        lowered = {s.lower() for s in candidate_skills}
        return lowered & set(required_skills)

    filtered = rows
    if required_skills:
        filtered = [r for r in rows if skill_overlap(r.Profile.skills or [])]

    # If skill filter returns nothing, fall back to all candidates (title/name match)
    if not filtered and required_skills:
        query_lower = query.lower()
        filtered = [
            r for r in rows
            if query_lower in (r.Profile.title or '').lower()
            or query_lower in r.User.full_name.lower()
            or any(query_lower in s.lower() for s in (r.Profile.skills or []))
        ]

    # If still nothing, return everyone
    if not filtered:
        filtered = rows

    # ── Step 4: Load appreciation aggregates ────────────────────────────────
    candidate_ids = [row.User.id for row in filtered]

    appr_stmt = (
        select(
            Appreciation.to_user_id,
            func.count(Appreciation.id).label("count"),
            func.avg(Appreciation.skill_rating).label("avg_skill"),
            func.avg(Appreciation.communication_rating).label("avg_comm"),
            func.avg(Appreciation.reliability_rating).label("avg_rel"),
        )
        .where(Appreciation.to_user_id.in_(candidate_ids))
        .group_by(Appreciation.to_user_id)
    )
    appr_rows = (await db.execute(appr_stmt)).all()
    appr_map: dict[uuid.UUID, dict] = {
        r.to_user_id: {
            "count": int(r.count),
            "avg_skill": float(r.avg_skill or 0),
            "avg_comm": float(r.avg_comm or 0),
            "avg_rel": float(r.avg_rel or 0),
        }
        for r in appr_rows
    }

    # ── Step 5: Rank each candidate ──────────────────────────────────────────
    results = []
    for row in filtered:
        user: User = row.User
        profile: Profile = row.Profile
        cs: CredibilityScore | None = row.CredibilityScore

        cred_score = cs.score if cs else 0
        candidate_skills = profile.skills or []

        if required_skills:
            matched = skill_overlap(candidate_skills)
            skill_overlap_pct = len(matched) / len(required_skills)
        else:
            skill_overlap_pct = 1.0

        appr = appr_map.get(user.id)
        if appr and appr["count"] > 0:
            avg_appr = (appr["avg_skill"] + appr["avg_comm"] + appr["avg_rel"]) / 3
            appr_count = appr["count"]
        else:
            avg_appr = 0.0
            appr_count = 0

        rank = (cred_score * 0.4) + (skill_overlap_pct * 40) + (avg_appr * 2)
        if trust_priority:
            rank += cred_score * 0.2

        results.append({
            "user_id": str(user.id),
            "uid": user.uid,
            "name": user.full_name,
            "title": profile.title,
            "skills": candidate_skills,
            "credibility_score": cred_score,
            "avg_appreciation": round(avg_appr, 1),
            "appreciation_count": appr_count,
            "skill_overlap_count": len(skill_overlap(candidate_skills)) if required_skills else len(candidate_skills),
            "rank_score": round(rank, 2),
        })

    results.sort(key=lambda r: r["rank_score"], reverse=True)
    return {"parsed": parsed, "results": results[:20]}
