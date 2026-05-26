import asyncio
import re
import uuid
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, literal

from src.models.user import User, UserRole
from src.models.profile import Profile
from src.models.credibility_score import CredibilityScore
from src.models.appreciation import Appreciation
from src.ai.search_prompt import parse_search_query

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Static lookup tables
# ---------------------------------------------------------------------------

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
    'frontend': ['react', 'reactjs', 'nextjs', 'javascript', 'typescript', 'html', 'css', 'tailwind', 'vue', 'angular', 'web'],
    'backend': ['api', 'node', 'nodejs', 'python', 'django', 'flask', 'java', 'go', 'postgres', 'database', 'server'],
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
    'psychologist': ['therapy', 'mental', 'health', 'assessment', 'behaviour'],
    'pharmacist': ['pharmacy', 'medication', 'prescription'],
    'developer': ['coding', 'software', 'web', 'app', 'programming'],
    'engineer': ['system', 'technical', 'code', 'software', 'development'],
}

_KNOWN_SKILLS = {
    'react', 'reactjs', 'nextjs', 'vue', 'angular', 'svelte', 'typescript', 'javascript',
    'python', 'node', 'nodejs', 'express', 'django', 'flask', 'java', 'go', 'php', 'laravel',
    'ruby', 'rails', 'html', 'css', 'tailwind', 'sass', 'postgres', 'postgresql', 'mysql',
    'mongodb', 'redis', 'graphql', 'rest', 'api', 'docker', 'kubernetes', 'aws', 'gcp', 'azure',
    'figma', 'ui', 'ux', 'machine learning', 'data science', 'devops', 'cloud', 'sql',
}

_STOP_WORDS = {
    'a', 'an', 'the', 'for', 'with', 'who', 'is', 'are', 'and', 'or', 'but', 'in', 'on',
    'at', 'to', 'of', 'looking', 'need', 'want', 'hire', 'find', 'someone', 'i', 'we',
    'our', 'my', 'good', 'great', 'please', 'help', 'can', 'could', 'would', 'should',
    'have', 'has', 'had', 'do', 'does', 'did', 'get', 'got', 'any', 'some', 'this',
    'that', 'these', 'those',
}

_SEARCH_FILLER_WORDS = {
    'reliable', 'trusted', 'trust', 'trustworthy', 'experienced', 'senior', 'expert',
    'honest', 'professional', 'certified', 'proven', 'deadline', 'deadlines',
    'deadline-driven', 'urgent', 'quick', 'fast', 'best', 'top', 'quality', 'great',
    'strong', 'good',
}

# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

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
    if any(cat not in {'developer', 'engineer'} for cat in matched_categories):
        profession_keywords = [
            kw for kw in profession_keywords
            if kw not in _PROFESSION_ALIASES['developer']
            and kw not in _PROFESSION_ALIASES['engineer']
        ]
    return _dedupe(profession_keywords), matched_categories


def _collect_skill_terms(text: str) -> list[str]:
    words = [w.strip('.,!?()') for w in text.split()]
    phrases = []
    for phrase in [
        'full stack', 'full-stack', 'machine learning', 'data science',
        'ui ux', 'ui/ux', 'mobile app', 'web development', 'back end',
        'front end', 'back-end', 'front-end', 'devops', 'cloud computing',
    ]:
        if phrase.replace('-', ' ') in text or phrase in text:
            phrases.append(phrase.replace('-', ' '))
    single_words = [
        w for w in words
        if w not in _STOP_WORDS and w not in _SEARCH_FILLER_WORDS and len(w) > 2
    ]
    skills = phrases + [w for w in single_words if w not in ' '.join(phrases)]
    normalized = _dedupe([s for s in skills if s in _KNOWN_SKILLS or ' ' in s])
    return normalized[:10] if normalized else _dedupe(skills)[:8]


def _expand_profession_terms(profession_keywords: list[str]) -> list[str]:
    expanded: list[str] = []
    for category, aliases in _PROFESSION_ALIASES.items():
        if any(alias in profession_keywords for alias in aliases):
            expanded.extend(_PROFESSION_EXPANSIONS.get(category, []))
    return _dedupe(expanded)


# ---------------------------------------------------------------------------
# Query intent parsing
# ---------------------------------------------------------------------------

def _simple_parse_fallback(query: str) -> dict:
    text = _normalize_query(query)
    words = [w.strip('.,!?()') for w in text.split()]
    profession_keywords, matched_categories = _collect_profession_terms(text)
    skills = _collect_skill_terms(text)
    if profession_keywords:
        all_aliases: set[str] = set()
        for items in _PROFESSION_ALIASES.values():
            all_aliases.update(items)
        skills = [s for s in skills if s not in all_aliases]

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
        'search_tier': search_tier,
        'profession_keywords': profession_keywords,
        'required_skills': skills,
        'trust_keywords': trust_words,
        'trust_priority': bool(trust_words),
        'experience_level': exp_level,
        'min_credibility_score': min_score,
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


# ---------------------------------------------------------------------------
# SQL search helpers (never loads more than 200 rows into Python)
# ---------------------------------------------------------------------------

def _sanitize_lexeme(term: str) -> str:
    """Strip non-word characters so a term is safe as a tsquery lexeme."""
    return re.sub(r'[^\w]', '', term.lower())


def _terms_to_or_tsquery(terms: list[str]) -> str | None:
    """
    Build 'word1 | word2 | word3' for to_tsquery.
    Multi-word terms ('software engineer') are split into individual words
    so each word becomes a valid tsquery lexeme.
    """
    lexemes: list[str] = []
    for term in terms:
        for word in re.sub(r'[^\w\s]', '', term.lower()).split():
            if len(word) >= 2:
                lexemes.append(word)
    # dedupe preserving order
    seen: set[str] = set()
    unique = [l for l in lexemes if not (l in seen or seen.add(l))]  # type: ignore[func-returns-value]
    if not unique:
        return None
    return ' | '.join(unique[:25])


def _terms_to_and_tsquery(terms: list[str]) -> str | None:
    """
    Build 'word1 & word2' for to_tsquery — ALL terms must appear.
    Used for required skills so candidates without them are excluded.
    """
    lexemes: list[str] = []
    for term in terms:
        lex = _sanitize_lexeme(term)
        if len(lex) >= 2:
            lexemes.append(lex)
    if not lexemes:
        return None
    return ' & '.join(lexemes[:8])


def _base_candidate_stmt(min_cred: int):
    """Shared base SELECT for all search strategies."""
    stmt = (
        select(User, Profile, CredibilityScore)
        .join(Profile, Profile.user_id == User.id)
        .outerjoin(CredibilityScore, CredibilityScore.user_id == User.id)
        .where(User.role == UserRole.candidate)
        .where(User.is_active == True)
    )
    if min_cred > 0:
        stmt = stmt.where(CredibilityScore.score >= min_cred)
    return stmt


def _profile_fts_expr():
    """
    Returns Profile.search_tsv — the stored tsvector column maintained by the
    database trigger (profiles_search_tsv_trigger). The GIN index is on this
    column so all FTS queries use it automatically.
    """
    return Profile.search_tsv


async def _fts_query(
    db: AsyncSession,
    required_skills: list[str],
    profession_keywords: list[str],
    rank_terms: list[str],
    min_cred: int,
) -> list:
    """
    Primary search: PostgreSQL full-text search using the GIN index.

    Filter strategy (two-level):
      - required_skills present → hard AND filter: profile MUST contain all of them
        (e.g. 'python & django' — Doctor/MobileApp dev are excluded immediately)
      - profession_keywords only → OR filter: any profession term matches

    Rank query uses all terms (skills + profession + expansions) via OR so that
    ts_rank reflects overall relevance, not just the filter terms.

    Returns at most 200 rows pre-ordered by ts_rank DESC.
    """
    fts = _profile_fts_expr()

    # --- build the WHERE filter ---
    if required_skills:
        # All required skills must appear in profile (AND)
        hard_str = _terms_to_and_tsquery(required_skills)
        if not hard_str:
            return []
        filter_tsq = func.to_tsquery('english', hard_str)
    elif profession_keywords:
        # Any profession keyword matches (OR)
        soft_str = _terms_to_or_tsquery(profession_keywords)
        if not soft_str:
            return []
        filter_tsq = func.to_tsquery('english', soft_str)
    else:
        return []

    # --- build the rank query (broader OR for better ts_rank signal) ---
    rank_str = _terms_to_or_tsquery(rank_terms)
    rank_tsq = func.to_tsquery('english', rank_str) if rank_str else filter_tsq

    ts_rank_col = func.ts_rank(fts, rank_tsq).label('_ts_rank')

    stmt = (
        _base_candidate_stmt(min_cred)
        .add_columns(ts_rank_col)
        .where(fts.op('@@')(filter_tsq))
        .order_by(ts_rank_col.desc())
        .limit(200)
    )
    try:
        return (await db.execute(stmt)).all()
    except Exception as exc:
        logger.warning("FTS query failed (%s), will try fuzzy fallback", exc)
        return []


async def _fuzzy_query(db: AsyncSession, raw_query: str, min_cred: int) -> list:
    """
    Fuzzy fallback: pg_trgm similarity on profile title.
    Catches typos like 'develoer' → 'developer'.
    Returns at most 50 rows.
    """
    sim_col = func.similarity(Profile.title, raw_query[:100]).label('_ts_rank')
    stmt = (
        _base_candidate_stmt(min_cred)
        .add_columns(sim_col)
        .where(func.similarity(Profile.title, raw_query[:100]) > 0.15)
        .order_by(sim_col.desc())
        .limit(50)
    )
    try:
        return (await db.execute(stmt)).all()
    except Exception as exc:
        logger.warning("Fuzzy query failed (%s), will try ILIKE fallback", exc)
        return []


async def _ilike_query(db: AsyncSession, terms: list[str], min_cred: int) -> list:
    """
    Last SQL fallback: ILIKE substring match on title and bio.
    No special index — only used when FTS and fuzzy both return nothing.
    Returns at most 100 rows.
    """
    conditions = []
    for term in terms[:5]:
        safe = term.replace('%', '').replace('_', '').replace('\\', '')
        if len(safe) >= 2:
            conditions.append(Profile.title.ilike(f'%{safe}%'))
            conditions.append(Profile.bio.ilike(f'%{safe}%'))
    if not conditions:
        return []

    placeholder_rank = literal(0.05).label('_ts_rank')
    stmt = (
        _base_candidate_stmt(min_cred)
        .add_columns(placeholder_rank)
        .where(or_(*conditions))
        .limit(100)
    )
    try:
        return (await db.execute(stmt)).all()
    except Exception as exc:
        logger.warning("ILIKE query failed (%s)", exc)
        return []


async def _load_appreciation_map(
    db: AsyncSession,
    candidate_ids: list[uuid.UUID],
) -> dict[uuid.UUID, dict]:
    """Batch-load appreciation aggregates for all candidates in one query."""
    if not candidate_ids:
        return {}
    stmt = (
        select(
            Appreciation.to_user_id,
            func.count(Appreciation.id).label('count'),
            func.avg(Appreciation.skill_rating).label('avg_skill'),
            func.avg(Appreciation.communication_rating).label('avg_comm'),
            func.avg(Appreciation.reliability_rating).label('avg_rel'),
        )
        .where(Appreciation.to_user_id.in_(candidate_ids))
        .group_by(Appreciation.to_user_id)
    )
    rows = (await db.execute(stmt)).all()
    return {
        r.to_user_id: {
            'count': int(r.count),
            'avg': (
                (float(r.avg_skill or 0) + float(r.avg_comm or 0) + float(r.avg_rel or 0)) / 3
            ),
        }
        for r in rows
    }


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------

def _skill_overlap(candidate_skills: list[str], required_skills: list[str]) -> set[str]:
    return {s.lower() for s in candidate_skills} & set(required_skills)


def _profession_title_exact(profile: Profile, profession_keywords: list[str]) -> bool:
    title_lower = (profile.title or '').lower()
    return any(kw in title_lower for kw in profession_keywords)


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
    appr_norm = avg_appr * 10  # 0–10 → 0–100
    return round(
        cred_score * 0.40
        + skill_match_pct * 100 * 0.35
        + appr_norm * 0.15
        + views_norm * 0.10
        + profession_exact_bonus,
        2,
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def search_candidates(query: str, db: AsyncSession) -> dict:
    """
    Search candidates using PostgreSQL full-text search (GIN indexed).

    Architecture:
      SQL pre-filter (≤200 rows) → Python ranking → top 20 results
      Fallback chain: tsvector FTS → pg_trgm fuzzy → ILIKE
      No data is ever loaded into Python without a SQL LIMIT.

    Returns empty results with a message when no candidates match —
    never returns random/unrelated profiles as a fallback.
    """
    # 1. Parse intent
    parsed = await _parse_search_intent(query)

    search_tier: str = parsed.get('search_tier', 'skill')
    profession_keywords: list[str] = parsed.get('profession_keywords', [])
    required_skills: list[str] = parsed.get('required_skills', [])
    trust_priority: bool = parsed.get('trust_priority', False)
    min_cred: int = int(parsed.get('min_credibility_score', 0))

    # "trust with deadlines" → filter out very-low-credibility candidates
    if trust_priority and min_cred < 25:
        min_cred = 25

    profession_terms = _dedupe(profession_keywords + _expand_profession_terms(profession_keywords))
    all_terms = _dedupe(required_skills + profession_terms)

    # 2. SQL-level search — never more than 200 rows enter Python
    # required_skills → hard AND filter (profile MUST have them all)
    # profession_keywords → OR filter (fallback when no skills specified)
    # rank_terms → broader OR used only for ts_rank ordering signal
    rows = await _fts_query(db, required_skills, profession_keywords, all_terms, min_cred)

    if not rows:
        # Fuzzy: use most specific extracted term to handle typos
        fuzzy_term = (required_skills + profession_keywords[:1] or [query])[0]
        rows = await _fuzzy_query(db, fuzzy_term, min_cred)

    if not rows:
        rows = await _ilike_query(db, all_terms, min_cred)

    # 3. No results → return empty with helpful message (no random fallback)
    if not rows:
        return {
            'parsed': parsed,
            'results': [],
            'search_tier_used': search_tier,
            'message': (
                'No candidates found matching your search. '
                'Try different skills, a broader role title, or check spelling.'
            ),
        }

    # 4. Batch load appreciation aggregates (single query, not N per candidate)
    candidate_ids = [r.User.id for r in rows]
    appr_map = await _load_appreciation_map(db, candidate_ids)

    # 5. Rank the ≤200 pre-filtered candidates in Python
    max_views = max((r.Profile.profile_views or 0) for r in rows) or 1

    results = []
    for row in rows:
        user: User = row.User
        profile: Profile = row.Profile
        cs: CredibilityScore | None = row.CredibilityScore

        cred_score = float(cs.score if cs else 0)
        candidate_skills = profile.skills or []
        appr = appr_map.get(user.id)
        avg_appr = appr['avg'] if appr else 0.0
        appr_count = appr['count'] if appr else 0

        if required_skills:
            matched = _skill_overlap(candidate_skills, required_skills)
            skill_match_pct = len(matched) / len(required_skills)
            if skill_match_pct == 0 and profession_keywords:
                # Has profession match but zero required skills → partial credit
                skill_match_pct = 0.2 if _profession_title_exact(profile, profession_keywords) else 0.0
        elif profession_keywords:
            exact_role = _profession_title_exact(profile, profession_keywords)
            skill_match_pct = 1.0 if exact_role else 0.5
        else:
            skill_match_pct = 1.0

        # Small tiebreaker bonus for exact profession title match — not large enough
        # to override a meaningful credibility score gap.
        profession_exact_bonus = (
            5.0 if _profession_title_exact(profile, profession_keywords)
            else 0.0
        ) if profession_keywords else 0.0

        cred_score_eff = cred_score * 1.2 if trust_priority else cred_score

        rank = _rank_score(
            cred_score_eff,
            skill_match_pct,
            avg_appr,
            profile.profile_views or 0,
            max_views,
            profession_exact_bonus,
        )

        results.append({
            'user_id': str(user.id),
            'uid': user.uid,
            'name': user.full_name,
            'title': profile.title,
            'skills': candidate_skills,
            'credibility_score': int(cred_score),
            'avg_appreciation': round(avg_appr, 1),
            'appreciation_count': appr_count,
            'skill_overlap_count': (
                len(_skill_overlap(candidate_skills, required_skills))
                if required_skills else len(candidate_skills)
            ),
            'rank_score': rank,
        })

    results.sort(key=lambda r: r['rank_score'], reverse=True)
    cap = 10 if search_tier == 'domain' else 20
    return {
        'parsed': parsed,
        'results': results[:cap],
        'search_tier_used': search_tier,
    }
