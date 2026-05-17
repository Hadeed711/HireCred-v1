"""
PDF CV text extraction and section-heading analysis.
Uses pdfplumber for PDF parsing. Only PDF is accepted.

Section matching compares CV headings against profile headings at a conceptual
level — not word-by-word — to catch when a CV is unrelated to the profile.
"""
import io
import re
import logging
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

# Canonical section heading keywords (lower-cased)
_SECTION_KEYWORDS = {
    "experience": {"experience", "work experience", "professional experience", "employment", "work history", "career"},
    "education": {"education", "academic", "qualifications", "degree", "university", "college", "schooling"},
    "skills": {"skills", "technical skills", "core competencies", "technologies", "expertise", "competencies", "tools"},
    "projects": {"projects", "portfolio", "personal projects", "key projects", "case studies", "work samples"},
    "certifications": {"certifications", "certificates", "licenses", "accreditations", "courses"},
    "summary": {"summary", "profile", "objective", "about", "introduction", "overview", "professional summary"},
    "contact": {"contact", "contact information", "personal information", "details"},
    "publications": {"publications", "papers", "research", "articles"},
    "awards": {"awards", "honors", "achievements", "accomplishments", "recognition"},
    "references": {"references", "referees"},
}

# Heading line patterns: ALL-CAPS line, or a line ending with colon, or markdown-style bold/header
_HEADING_RE = re.compile(
    r"^(?:[A-Z][A-Z\s&/\-]{3,}|[A-Z][a-zA-Z\s&/\-]+:|\#{1,3}\s+.+)$"
)


def extract_cv_text_and_sections(pdf_bytes: bytes) -> dict:
    """
    Extract plain text + detected section headings from a PDF CV.

    Returns:
        {
            "text": str,           # full extracted text (up to 6000 chars)
            "sections": list[str], # detected section heading labels (canonical names)
            "raw_headings": list[str],  # verbatim heading lines found
            "word_count": int,
        }
    """
    try:
        import pdfplumber
    except ImportError:
        logger.error("pdfplumber not installed")
        return {"text": "", "sections": [], "raw_headings": [], "word_count": 0}

    text_parts = []
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                text_parts.append(page_text)
    except Exception as exc:
        logger.warning("pdfplumber failed to open PDF: %s", exc)
        return {"text": "", "sections": [], "raw_headings": [], "word_count": 0}

    full_text = "\n".join(text_parts)
    words = full_text.split()
    raw_headings, sections = _detect_sections(full_text)

    return {
        "text": full_text[:6000],
        "sections": sections,
        "raw_headings": raw_headings,
        "word_count": len(words),
    }


def _detect_sections(text: str) -> tuple[list[str], list[str]]:
    """Return (raw_heading_lines, canonical_section_names) found in text."""
    raw_headings: list[str] = []
    canonical: list[str] = []
    seen_canonical: set[str] = set()

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or len(stripped) < 3 or len(stripped) > 60:
            continue
        if _HEADING_RE.match(stripped):
            raw_headings.append(stripped)
            canon = _canonicalize(stripped)
            if canon and canon not in seen_canonical:
                canonical.append(canon)
                seen_canonical.add(canon)

    return raw_headings, canonical


def _canonicalize(heading: str) -> str | None:
    """Map a heading string to a canonical section name."""
    clean = heading.rstrip(":").strip().lower()
    for canon, variants in _SECTION_KEYWORDS.items():
        if clean in variants:
            return canon
        # Fuzzy partial match
        for variant in variants:
            if variant in clean or clean in variant:
                return canon
            if SequenceMatcher(None, clean, variant).ratio() > 0.82:
                return canon
    return None


def compute_cv_profile_match(cv_data: dict, profile_data: dict) -> dict:
    """
    Compare CV sections and title against the profile's own data.

    Matching strategy (heading-level, not word-level):
    - Does CV have an experience section? → check if profile has experience entries.
    - Does CV title/summary mention the same profession as profile.title?
    - Do CV skills keywords overlap with profile.skills?
    - If CV is empty / too short → automatic penalty flag.

    Returns:
        {
            "match_score": int,       # 0-100 — how well CV maps to profile
            "warnings": list[str],    # human-readable penalty reasons
            "passed": bool,
        }
    """
    warnings: list[str] = []
    bonus = 0

    word_count = cv_data.get("word_count", 0)
    sections = cv_data.get("sections", [])
    cv_text = (cv_data.get("text") or "").lower()

    # ── Empty / useless CV ────────────────────────────────────────────────────
    if word_count < 50:
        return {
            "match_score": 0,
            "warnings": ["CV is empty or contains too little content (fewer than 50 words)."],
            "passed": False,
        }

    if word_count < 80:
        warnings.append(f"CV is very short ({word_count} words); a real resume should have at least 80.")

    # ── Section presence checks ───────────────────────────────────────────────
    has_experience_section = "experience" in sections
    has_skills_section = "skills" in sections
    has_education_section = "education" in sections

    profile_experience = profile_data.get("experience") or []
    profile_skills = profile_data.get("skills") or []
    profile_title = (profile_data.get("title") or "").lower()

    # If profile has experience but CV has no experience section → mismatch
    if profile_experience and not has_experience_section:
        warnings.append("CV has no recognizable Experience section, but profile lists work experience.")
    elif has_experience_section and profile_experience:
        bonus += 25
        # Deep check: do any CV experience titles/companies appear in CV text?
        for exp in profile_experience[:4]:
            company = (exp.get("company") or "").lower()
            title = (exp.get("title") or "").lower()
            if company and company in cv_text:
                bonus += 5
            elif title and title in cv_text:
                bonus += 3

    # Skills overlap
    if profile_skills and has_skills_section:
        matched_skills = sum(1 for s in profile_skills if s.lower() in cv_text)
        skill_overlap_pct = matched_skills / len(profile_skills)
        if skill_overlap_pct >= 0.5:
            bonus += 20
        elif skill_overlap_pct >= 0.25:
            bonus += 10
            warnings.append("Only a few of the listed skills appear in the CV.")
        else:
            warnings.append("Almost none of the profile skills appear in the CV; they may be mismatched.")
    elif profile_skills and not has_skills_section:
        warnings.append("CV has no Skills section, but profile lists skills.")

    # Title/profession check
    if profile_title:
        title_words = [w for w in profile_title.split() if len(w) > 3]
        title_match = any(w in cv_text for w in title_words)
        if title_match:
            bonus += 15
        else:
            warnings.append(
                f'Profile title "{profile_data.get("title")}" was not found in the CV — '
                "this may indicate a mismatch."
            )

    # Education section bonus (just presence)
    if has_education_section:
        bonus += 10

    # No sections detected at all
    if not sections:
        warnings.append(
            "No standard CV sections (Experience, Skills, Education, etc.) were detected. "
            "The CV may be unstructured or contain only images/scanned text."
        )

    match_score = min(100, max(0, bonus))
    passed = match_score >= 30 and len(warnings) <= 2

    return {
        "match_score": match_score,
        "warnings": warnings,
        "passed": passed,
    }
