import asyncio
import re
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

_PROFESSION_ALIASES: dict[str, list[str]] = {
    'frontend': [
        'frontend', 'front end', 'front-end', 'frontend engineer', 'frontend developer',
        'ui engineer', 'ui developer', 'ui/ux', 'ui ux', 'react developer', 'web developer',
    ],
    'backend': [
        'backend', 'back end', 'back-end', 'backend engineer', 'backend developer',
        'api developer', 'server engineer', 'server developer',
    ],
    'full stack': [
        'full stack', 'full-stack', 'fullstack', 'full stack developer', 'full stack engineer',
    ],
    'designer': [
        'designer', 'ui ux designer', 'ui/ux designer', 'product designer', 'ux designer',
        'visual designer', 'graphic designer',
    ],
    'electrician': ['electrician', 'electrical technician', 'electrical engineer'],
    'plumber': ['plumber', 'plumbing technician', 'pipe fitter'],
    'doctor': ['doctor', 'physician', 'medical doctor'],
    'lawyer': ['lawyer', 'attorney', 'advocate'],
    'nurse': ['nurse', 'registered nurse'],
    'teacher': ['teacher', 'educator', 'tutor'],
    'accountant': ['accountant', 'bookkeeper', 'auditor'],
    'architect': ['architect', 'architectural designer'],
    'pilot': ['pilot', 'aviator'],
    'psychologist': ['psychologist', 'therapist', 'counsellor', 'counselor'],
    'pharmacist': ['pharmacist'],
    'developer': ['developer', 'software developer', 'software engineer', 'programmer'],
    'engineer': ['engineer', 'software engineer', 'systems engineer'],
}

_PROFESSION_EXPANSIONS: dict[str, list[str]] = {
    'frontend': ['react', 'react.js', 'next.js', 'javascript', 'typescript', 'html', 'css', 'tailwind', 'vue', 'angular', 'web'],
    'backend': ['api', 'node', 'node.js', 'python', 'django', 'flask', 'java', 'go', 'postgres', 'database', 'server'],
    'full stack': ['frontend', 'backend', 'web', 'api', 'javascript', 'typescript', 'react', 'node'],
    'designer': ['figma', 'wireframe', 'prototype', 'ui', 'ux', 'branding', 'visual'],
    'electrician': ['electrical', 'wiring', 'circuits', 'installation', 'maintenance', 'repair', 'power'],
    'plumber': ['pipes', 'pipe', 'fixtures', 'drain', 'water', 'installation', 'maintenance'],
    'doctor': ['clinical', 'medical', 'patient', 'health', 'hospital'],
    'lawyer': ['legal', 'law', 'court', 'contract', 'compliance'],
    'nurse': ['clinical', 'patient', 'hospital', 'care'],
    'teacher': ['education', 'classroom', 'curriculum', 'lesson'],
    'accountant': ['tax', 'audit', 'bookkeeping', 'finance', 'reporting'],
    'architect': ['building', 'design', 'construction', 'blueprint'],
    'pilot': ['aviation', 'flight', 'aircraft', 'navigation'],
    'psychologist': ['therapy', 'mental health', 'assessment', 'behaviour'],
    'pharmacist': ['pharmacy', 'medication', 'prescription'],
    'developer': ['coding', 'software', 'web', 'app', 'programming'],
    'engineer': ['system', 'technical', 'code', 'software', 'development'],
}

_KNOWN_SKILLS = {
    'react', 'react.js', 'next.js', 'vue', 'angular', 'svelte', 'typescript', 'javascript',
    'python', 'node', 'node.js', 'express', 'django', 'flask', 'java', 'go', 'php', 'laravel',
    'ruby', 'rails', 'html', 'css', 'tailwind', 'sass', 'postgres', 'postgresql', 'mysql',
    'mongodb', 'redis', 'graphql', 'rest', 'api', 'docker', 'kubernetes', 'aws', 'gcp', 'azure',
    'figma', 'ui', 'ux', 'ui/ux', 'machine learning', 'data science', 'devops', 'cloud', 'sql',
}

_STOP_WORDS = {
    'a','an','the','for','with','who','is','are','and','or','but','in','on','at','to','of',
    'looking','need','want','hire','find','someone','i','we','our','my','good','great',
    'please','help','can','could','would','should','have','has','had','do','does','did',
    'get','got','any','some','this','that','these','those',
}

_SEARCH_FILLER_WORDS = {
    'reliable', 'trusted', 'trust', 'trustworthy', 'experienced', 'senior', 'expert',
    'honest', 'professional', 'certified', 'proven', 'deadline', 'deadlines', 'deadline-driven',
    'urgent', 'quick', 'fast', 'best', 'top', 'quality', 'great', 'strong', 'good',
}


def _normalize_query(query: str) -> str:
    return re.sub(r'\s+', ' ', query.lower()).strip()


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))


def _collect_profession_terms(text: str) -> tuple[list[str], list[str]]:
    profession_keywords: list[str] = []
    matched_categories: list[str] = []

    for category, aliases in _PROFESSION_ALIASES.items():
        if any(alias in text for alias in aliases):
            matched_categories.append(category)
            profession_keywords.extend(aliases)

    if any(category not in {'developer', 'engineer'} for category in matched_categories):
        profession_keywords = [kw for kw in profession_keywords if kw not in _PROFESSION_ALIASES['developer'] and kw not in _PROFESSION_ALIASES['engineer']]

    return _dedupe(profession_keywords), matched_categories


def _collect_skill_terms(text: str) -> list[str]:
    words = [w.strip('.,!?()') for w in text.split()]
    phrases = []
    for phrase in ['full stack', 'full-stack', 'machine learning', 'data science',
                   'ui ux', 'ui/ux', 'mobile app', 'web development', 'back end',
                   'front end', 'back-end', 'front-end', 'devops', 'cloud computing']:
        if phrase.replace('-', ' ') in text or phrase in text:
            phrases.append(phrase.replace('-', ' '))

    single_words = [w for w in words if w not in _STOP_WORDS and w not in _SEARCH_FILLER_WORDS and len(w) > 2]
    skills = phrases + [w for w in single_words if w not in ' '.join(phrases)]

    normalized = _dedupe([s for s in skills if s in _KNOWN_SKILLS or ' ' in s])
    if normalized:
        return normalized[:10]

    return _dedupe(skills)[:8]


def _all_profession_aliases() -> set[str]:
    aliases: set[str] = set()
    for items in _PROFESSION_ALIASES.values():
        aliases.update(items)
    return aliases


def _expand_profession_terms(profession_keywords: list[str]) -> list[str]:
    expanded: list[str] = []
    for category, aliases in _PROFESSION_ALIASES.items():
        if any(alias in profession_keywords for alias in aliases):
            expanded.extend(_PROFESSION_EXPANSIONS.get(category, []))
    return _dedupe(expanded)


def _profile_text(profile: Profile) -> str:
    return " ".join([
        (profile.title or '').lower(),
        (profile.bio or '').lower(),
        ' '.join(s.lower() for s in (profile.skills or [])),
        ' '.join(
            f"{e.get('title','')} {e.get('company','')} {e.get('description','')}".lower()
            for e in (profile.experience or [])
        ),
    ])


def _profile_matches_terms(profile: Profile, terms: list[str]) -> bool:
    text = _profile_text(profile)
    return any(term in text for term in terms if term)


def _simple_parse_fallback(query: str) -> dict:
    text = _normalize_query(query)
    words = [w.strip('.,!?()') for w in text.split()]
    profession_keywords, matched_categories = _collect_profession_terms(text)
    skills = _collect_skill_terms(text)
    if profession_keywords:
        profession_aliases = _all_profession_aliases()
        skills = [s for s in skills if s not in profession_aliases]

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

    search_tier = 'profession' if profession_keywords else 'skill'
    if not profession_keywords and not skills:
        search_tier = 'domain'

    return {
        "search_tier": search_tier,
        "profession_keywords": profession_keywords,
        "required_skills": skills,
        "trust_keywords": trust_words,
        "trust_priority": bool(trust_words),
        "experience_level": exp_level,
        "min_credibility_score": min_score,
    }


async def _parse_search_intent(query: str) -> dict:
    local = _simple_parse_fallback(query)
    if local.get('search_tier') == 'profession' or local.get('required_skills'):
        return local

    try:
        parsed = await asyncio.wait_for(parse_search_query(query), timeout=3.5)
    except Exception:
        return local

    parsed['required_skills'] = _dedupe([s.lower().strip() for s in parsed.get('required_skills', [])])
    parsed['profession_keywords'] = _dedupe([p.lower().strip() for p in parsed.get('profession_keywords', [])])
    parsed.setdefault('search_tier', local.get('search_tier', 'skill'))
    parsed.setdefault('trust_keywords', [])
    parsed.setdefault('trust_priority', False)
    parsed.setdefault('experience_level', None)
    parsed.setdefault('min_credibility_score', 0)

    if not parsed.get('profession_keywords') and local.get('profession_keywords'):
        parsed['profession_keywords'] = local['profession_keywords']
    if not parsed.get('required_skills') and local.get('required_skills'):
        parsed['required_skills'] = local['required_skills']
    if local.get('search_tier') == 'profession':
        parsed['search_tier'] = 'profession'
    elif local.get('search_tier') == 'domain' and not parsed.get('profession_keywords') and not parsed.get('required_skills'):
        parsed['search_tier'] = 'domain'
    return parsed


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
    parsed = await _parse_search_intent(query)

    search_tier: str = parsed.get("search_tier", "skill")
    profession_keywords: list[str] = parsed.get("profession_keywords", [])
    required_skills: list[str] = parsed.get("required_skills", [])
    trust_priority: bool = parsed.get("trust_priority", False)
    min_cred: int = int(parsed.get("min_credibility_score", 0))
    profession_terms = _dedupe(profession_keywords + _expand_profession_terms(profession_keywords))
    query_terms = _dedupe(required_skills + profession_terms)

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
        exact_matches = [r for r in rows if _profession_title_exact(r.Profile, profession_keywords)]
        if exact_matches:
            filtered = exact_matches
            tier_used = "profession"
        else:
            related_matches = [r for r in rows if _profile_matches_terms(r.Profile, query_terms)]
            if related_matches:
                filtered = related_matches
                tier_used = "profession"

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
        fallback_terms = query_terms or [token for token in query_lower.split() if token not in _STOP_WORDS]
        filtered = [r for r in rows if _profile_matches_terms(r.Profile, fallback_terms)]
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
            exact_role = _profession_title_exact(profile, profession_keywords)
            related_role = _profile_matches_terms(profile, query_terms)
            # Keep role searches strict enough to rank the right profession first.
            skill_match_pct = 1.0 if exact_role else (0.8 if related_role else 0.5)
        else:
            skill_match_pct = 1.0

        if profession_keywords:
            profession_exact = 35.0 if _profession_title_exact(profile, profession_keywords) else (15.0 if _profile_matches_terms(profile, query_terms) else 0.0)
        else:
            profession_exact = 0.0

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
