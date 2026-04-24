from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.middleware.auth import get_current_user
from src.models.user import User
from src.services.search_service import search_candidates

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
    required_skills: list[str]
    trust_keywords: list[str]
    trust_priority: bool
    experience_level: str | None = None
    min_credibility_score: int = 0


class SearchResponse(BaseModel):
    parsed: ParsedIntent
    results: list[CandidateResult]


@router.post("", response_model=SearchResponse)
async def search(
    body: SearchRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await search_candidates(body.query.strip(), db)
    return result
