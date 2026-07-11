from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.middleware.auth import get_current_user
from src.models.user import User
from src.services.search_service import search_candidates
from src.rate_limiter import limiter

router = APIRouter(prefix="/api/search", tags=["search"])


class SearchRequest(BaseModel):
    query: str


class CandidateResult(BaseModel):
    user_id: str
    uid: int | None = None
    name: str
    title: str | None
    skills: list[str]
    credibility_score: int
    avg_appreciation: float
    appreciation_count: int
    skill_overlap_count: int
    rank_score: float


class ParsedIntent(BaseModel):
    search_tier: str = "skill"
    profession_keywords: list[str] = []
    required_skills: list[str]
    trust_keywords: list[str]
    trust_priority: bool
    experience_level: str | None = None
    min_credibility_score: int = 0


class SearchResponse(BaseModel):
    parsed: ParsedIntent
    results: list[CandidateResult]
    search_tier_used: str = "skill"


@router.post("", response_model=SearchResponse)
@limiter.limit("30/minute")
async def search(
    request: Request,
    body: SearchRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = body.query.strip()
    if len(q) < 2:
        raise HTTPException(status_code=400, detail="Search query must be at least 2 characters.")
    if len(q) > 500:
        raise HTTPException(status_code=400, detail="Search query must be 500 characters or fewer.")
    result = await search_candidates(q, db)
    return result
