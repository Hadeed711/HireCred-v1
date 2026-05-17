"""
Validation API endpoints used by the frontend for real-time checks.
"""
from fastapi import APIRouter
from pydantic import BaseModel

from src.services.skill_validator import validate_skills, skill_domain
from src.services.url_checker import check_url

router = APIRouter(prefix="/api/validate", tags=["validate"])


# ── Skill validation ──────────────────────────────────────────────────────────

class SkillsBody(BaseModel):
    skills: list[str]


@router.post("/skills")
async def validate_skills_endpoint(body: SkillsBody):
    return validate_skills(body.skills)


# ── URL reachability ──────────────────────────────────────────────────────────

class UrlBody(BaseModel):
    url: str


@router.post("/url")
async def validate_url_endpoint(body: UrlBody):
    return await check_url(body.url)


# ── Title consistency ─────────────────────────────────────────────────────────

_TITLE_DOMAIN_MAP = {
    "tech": [
        "developer","engineer","programmer","software","backend","frontend","fullstack",
        "full-stack","full stack","data scientist","ml","ai","devops","architect",
        "sre","cloud","web","mobile","ios","android","qa","tester","analyst",
    ],
    "medical": [
        "doctor","physician","surgeon","nurse","dentist","pharmacist","therapist",
        "psychologist","cardiologist","radiologist","pediatrician","psychiatrist",
        "medical","clinical","healthcare","gp","specialist",
    ],
    "legal": [
        "lawyer","attorney","counsel","paralegal","solicitor","barrister","judge",
        "legal","advocate","law",
    ],
    "culinary": [
        "chef","cook","baker","pastry","culinary","restaurant","kitchen",
    ],
    "design": [
        "designer","creative","ui","ux","graphic","visual","illustrator","art director",
    ],
    "finance": [
        "accountant","auditor","banker","cfo","cpa","bookkeeper","financial",
        "analyst","treasurer","actuary",
    ],
    "education": [
        "teacher","professor","tutor","instructor","lecturer","educator","trainer",
    ],
}

_INCOMPATIBLE = {
    "tech": {"medical","legal","culinary"},
    "medical": {"tech","culinary","legal"},
    "legal": {"medical","culinary","tech"},
    "culinary": {"tech","medical","legal","finance"},
}


def _title_domain(title: str) -> str | None:
    lower = title.lower()
    for domain, keywords in _TITLE_DOMAIN_MAP.items():
        if any(kw in lower for kw in keywords):
            return domain
    return None


class ConsistencyBody(BaseModel):
    title: str
    skills: list[str]


@router.post("/consistency")
async def check_consistency(body: ConsistencyBody):
    if not body.title or not body.skills:
        return {"consistent": True, "warning": None}

    t_domain = _title_domain(body.title)
    s_domain = skill_domain(body.skills)

    if t_domain and s_domain and s_domain in _INCOMPATIBLE.get(t_domain, set()):
        return {
            "consistent": False,
            "warning": (
                f'Your title says "{body.title}" ({t_domain}) but your skills are mostly '
                f'{s_domain}-related. Make sure your profile tells a consistent story.'
            ),
        }
    return {"consistent": True, "warning": None}
