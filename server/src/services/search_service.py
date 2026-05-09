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
    words = [w.strip('.,!?()') for w in query.lower().split()]
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

    min_score = 0
    if any(p in text for p in ['high credibility', 'high trust', 'highly trusted', 'top credibility', 'most trusted']):
        min_score = 70
    elif any(p in text for p in ['moderate credibility', 'average trust', 'medium trust']):
        min_score = 40

    return {
        "search_tier": "skill",
        "profession_keywords": [],
        "required_skills": skills[:8],
        "trust_keywords": trust_words,
        "trust_priority": bool(trust_words),
        "experience_level": exp_level,
        "min_credibility_score": min_score,
    }


def _profession_match(profile: Profile, profession_keywords: list[str]) -> bool:
    """True if the candidate's title or skills contain any profession keyword."""
    title_lower = (profile.title or "").lower()
    skills_lower = {s.lower() for s in (profile.skills or [])}
    for kw in profession_keywords:
        if kw in title_lower:
            return True
        if any(kw in s for s in skills_lower):
            return True
    return False


def _profession_title_exact(profile: Profile, profession_keywords: list[str]) -> bool:
    """True if the candidate's title exactly contains a profession keyword."""
    title_lower = (profile.title or "").lower()
    return any(kw in title_lower for kw in profession_keywords)


def _skill_overlap(candidate_skills: list[str], required_skills: list[str]) -> set[str]:
    lowered = {s.lower() for s in candidate_skills}
    return lowered & set(required_skills)


def _domain_match(profile: Profile, query_lower: str) -> bool:
    """Loose domain match: check bio, skills, and experience text for query tokens."""
    tokens = [t for t in query_lower.split() if t not in _STOP_WORDS and len(t) > 2]
    if not tokens:
        return True
    text = " ".join([
        (profile.bio or "").lower(),
        " ".join(s.lower() for s in (profile.skills or [])),
        " ".join(
            f"{e.get('title','')} {e.get('company','')} {e.get('description','')}".lower()
            for e in (profile.experience or [])
        ),
    ])
    return any(token in text for token in tokens)


def _rank_score(
    cred_score: float,
    skill_match_pct: float,
    avg_appr: float,
    profile_views: int,
    max_views: int,
    profession_exact_bonus: float = 0.0,
) -> float:
    """Composite ranking: credibility 40%, skill 35%, appreciation 15%, views 10%."""
    views_norm = (profile_views / max_views * 100) if max_views > 0 else 0
    appr_norm = avg_appr * 10  # 0-10 → 0-100
    score = (
        cred_score * 0.40
        + skill_match_pct * 100 * 0.35
        + appr_norm * 0.15
        + views_norm * 0.10
        + profession_exact_bonus
    )
    return round(score, 2)


async def search_candidates(query: str, db: AsyncSession) -> dict:
    """Three-tier search: profession exact → skill semantic → domain fallback."""

    # Step 1: Parse intent
    try:
        parsed = await parse_search_query(query)
    except Exception:
        logger.warning("AI search parsing failed, using keyword fallback")
        parsed = _simple_parse_fallback(query)

    search_tier: str = parsed.get("search_tier", "skill")
    profession_keywords: list[str] = parsed.get("profession_keywords", [])
    required_skills: list[str] = parsed.get("required_skills", [])
    trust_priority: bool = parsed.get("trust_priority", False)
    min_cred: int = int(parsed.get("min_credibility_score", 0))

    # Step 2: Load all candidates
    stmt = (
        select(User, Profile, CredibilityScore)
        .join(Profile, Profile.user_id == User.id)
        .outerjoin(CredibilityScore, CredibilityScore.user_id == User.id)
        .where(User.role == UserRole.candidate)
        .where(User.is_active == True)
    )
    rows = (await db.execute(stmt)).all()

    if not rows:
        return {"parsed": parsed, "results": [], "search_tier_used": search_tier}

    # Apply minimum credibility filter
    if min_cred > 0:
        rows = [r for r in rows if r.CredibilityScore and r.CredibilityScore.score >= min_cred]

    # Step 3: Tiered filtering
    query_lower = query.lower()
    filtered = []
    tier_used = search_tier

    # Tier 1 — exact profession match
    if search_tier == "profession" and profession_keywords:
        filtered = [r for r in rows if _profession_match(r.Profile, profession_keywords)]
        if not filtered:
            # Fall through to Tier 2
            tier_used = "skill"

    # Tier 2 — skill overlap
    if not filtered:
        if required_skills:
            filtered = [r for r in rows if _skill_overlap(r.Profile.skills or [], required_skills)]
        if not filtered and required_skills:
            # Partial title/name match fallback
            filtered = [
                r for r in rows
                if any(kw in (r.Profile.title or "").lower() for kw in required_skills + profession_keywords)
                or any(kw in r.User.full_name.lower() for kw in required_skills + profession_keywords)
            ]
        if filtered:
            tier_used = "skill"

    # Tier 3 — domain semantic fallback (search all text)
    if not filtered:
        filtered = [r for r in rows if _domain_match(r.Profile, query_lower)]
        tier_used = "domain"

    # Last resort: return all candidates
    if not filtered:
        filtered = rows
        tier_used = "domain"

    # Step 4: Load appreciation aggregates
    candidate_ids = [r.User.id for r in filtered]
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
            "avg": ((float(r.avg_skill or 0) + float(r.avg_comm or 0) + float(r.avg_rel or 0)) / 3),
        }
        for r in appr_rows
    }

    # Step 5: Rank
    max_views = max((r.Profile.profile_views or 0) for r in filtered) or 1

    results = []
    for row in filtered:
        user: User = row.User
        profile: Profile = row.Profile
        cs: CredibilityScore | None = row.CredibilityScore

        cred_score = float(cs.score if cs else 0)
        candidate_skills = profile.skills or []
        appr = appr_map.get(user.id)
        avg_appr = appr["avg"] if appr else 0.0
        appr_count = appr["count"] if appr else 0

        if required_skills:
            matched = _skill_overlap(candidate_skills, required_skills)
            skill_match_pct = len(matched) / len(required_skills)
        elif profession_keywords:
            # For profession tier, treat matching keywords as 100%
            skill_match_pct = 1.0 if _profession_match(profile, profession_keywords) else 0.5
        else:
            skill_match_pct = 1.0

        profession_exact = 15.0 if (profession_keywords and _profession_title_exact(profile, profession_keywords)) else 0.0

        if trust_priority:
            cred_score_eff = cred_score * 1.2
        else:
            cred_score_eff = cred_score

        rank = _rank_score(
            cred_score_eff,
            skill_match_pct,
            avg_appr,
            profile.profile_views or 0,
            max_views,
            profession_exact,
        )

        results.append({
            "user_id": str(user.id),
            "uid": user.uid,
            "name": user.full_name,
            "title": profile.title,
            "skills": candidate_skills,
            "credibility_score": int(cred_score),
            "avg_appreciation": round(avg_appr, 1),
            "appreciation_count": appr_count,
            "skill_overlap_count": len(_skill_overlap(candidate_skills, required_skills)) if required_skills else len(candidate_skills),
            "rank_score": rank,
        })

    results.sort(key=lambda r: r["rank_score"], reverse=True)
    cap = 6 if tier_used == "domain" else 20
    return {
        "parsed": parsed,
        "results": results[:cap],
        "search_tier_used": tier_used,
    }
