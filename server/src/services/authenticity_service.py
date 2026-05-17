"""
Profile authenticity heuristics — detects fake, duplicate, boilerplate,
sci-fi/fantasy, and suspicious accounts without blocking any saves.
All findings are returned as scored penalty flags that feed into the
credibility scoring pipeline.

Detection signals:
1.  Bio boilerplate / template text
2.  Extremely generic or suspicious name patterns
3.  Copy-paste experience descriptions (identical across entries)
4.  Future-dated experience (including far-future years like 3020)
5.  Portfolio all using same domain / identical descriptions
6.  Skills that look copied (30+ skills, all very generic)
7.  Sci-fi / fantasy content in bio, title, experience, portfolio
8.  Joke / non-professional skills (coffee drinking, meme design, etc.)
9.  Absurd numeric claims (999 years of experience, 5000% increase)
10. Suspicious title patterns (pixel wizard, supreme overlord, etc.)
11. Fictional location detection (Mars Colony, Sector 9, etc.)
12. Fictional company / org names (Galaxy Banana Corp, etc.)
13. Suspicious email patterns (disposable/numbered accounts)
14. URL reachability failures in portfolio / proof signals
"""
import re
import logging
from datetime import datetime, timezone
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

_CURRENT_YEAR = datetime.now(timezone.utc).year

# ── Boilerplate bio phrases ────────────────────────────────────────────────────
_BOILERPLATE_PHRASES = [
    "lorem ipsum", "write your bio", "about me section", "insert bio",
    "your bio here", "add your description", "click to edit", "i am a professional",
    "experienced professional", "passionate about", "i am passionate",
    "highly motivated", "team player", "results-driven", "dynamic professional",
    "leverage my skills", "seeking opportunities", "innovative solutions",
    "out-of-the-box thinking", "synergy", "paradigm shift", "thought leader",
    "guru", "ninja", "rockstar", "wizard", "evangelist", "visionary",
    "dedicated professional", "seasoned professional", "proven track record",
]

# ── Suspicious name patterns ───────────────────────────────────────────────────
_SUSPICIOUS_NAME_RE = re.compile(
    r"^(test|dummy|fake|user|admin|sample|john doe|jane doe|mr\.|ms\.|"
    r"asdf|qwerty|abc|xyz|foo|bar|lorem|ipsum)[^a-z]*$",
    re.IGNORECASE,
)

# ── Disposable / suspicious email patterns ─────────────────────────────────────
_DISPOSABLE_DOMAINS = {
    "mailinator.com", "guerrillamail.com", "tempmail.com", "throwaway.email",
    "sharklasers.com", "guerrillamailblock.com", "grr.la", "yopmail.com",
    "10minutemail.com", "trashmail.com", "dispostable.com", "spamgourmet.com",
    "fakeinbox.com", "maildrop.cc", "spam4.me", "getairmail.com",
}

# ── Sci-fi / fantasy keywords (in any content field) ──────────────────────────
_SCIFI_PHRASES = {
    "hologram", "holographic", "intergalactic", "alien startup", "alien company",
    "alien client", "extraterrestrial", "robotic compan", "robot compan",
    "mars colony", "moon base", "moon colony", "space colony", "space station",
    "galaxy banana", "galactic market", "banana corp", "sandwich studio",
    "floating billboard", "floating hologram", "jetpack cat", "jetpack",
    "time travel", "time-travel", "teleport", "warp speed", "lightsaber",
    "outer space client", "multiple galaxies", "across galaxies",
    "across multiple galaxies", "interplanetary", "intergalactic market",
    "alien startup", "robot startup", "cyborg company", "neon branding",
    "imaginary client", "imaginary project", "potato in outer space",
    "luxury potato", "banana sales on jupiter", "banana on jupiter",
    "banana on saturn", "banana on mars", "invisible website", "invisible ui",
    "transparent website", "neon potato",
}

# Looser single-word sci-fi signals (require extra context to flag)
_SCIFI_WORDS = {
    "hologram", "holographic", "intergalactic", "extraterrestrial",
    "galactic", "martian", "cyborg", "teleporter", "lightsaber",
}

# ── Fictional / impossible location indicators ─────────────────────────────────
_FICTIONAL_LOCATION_RE = re.compile(
    r"\b(mars|moon base|moon colony|outer space|space station|intergalactic|"
    r"galaxy|sector\s*\d+|planet\s+\w+|lunar\s+base|orbit|asteroid|nebula|"
    r"milky way|andromeda|jupiter|saturn|pluto|uranus|neptune|mercury\s+colony|"
    r"venus\s+colony|dimension\s*\d+|virtual\s+realm)\b",
    re.IGNORECASE,
)

# ── Joke / non-professional skills ────────────────────────────────────────────
_JOKE_SKILL_WORDS = {
    "coffee drinking", "coffee", "meme design", "meme", "random creativity",
    "fake skill", "laser design", "space branding", "quantum photoshop",
    "galactic ui", "rgb mastery", "pixel manipulation", "procrastination",
    "breathing", "sleeping", "eating", "daydreaming", "nap taking",
    "scrolling", "binge watching", "random skill", "useless skill",
    "skill 101", "imaginary skill", "invisible skill", "fake 101",
}

# ── Absurd title keywords ─────────────────────────────────────────────────────
_ABSURD_TITLE_RE = re.compile(
    r"\b(ultra\s+creative|pixel\s+wizard|supreme\s+overlord|mega\s+guru|"
    r"cosmic\s+designer|galactic|intergalactic|space\s+wizard|time\s+travell?er|"
    r"quantum\s+wizard|alien\s+designer|martian\s+dev|overlord|dark\s+lord|"
    r"grand\s+master\s+of\s+|ninja\s+of\s+|rockstar\s+of\s+|wizard\s+of\s+)\b",
    re.IGNORECASE,
)

# ── Fictional company name indicators ─────────────────────────────────────────
_FICTIONAL_COMPANY_RE = re.compile(
    r"\b(galaxy\s+banana|banana\s+corp|moonlight\s+sandwich|sandwich\s+studio|"
    r"galactic\s+corp|intergalactic\s+|cosmic\s+corp|alien\s+corp|robot\s+corp|"
    r"neon\s+potato|hologram\s+inc|jetpack\s+|floating\s+corp|mars\s+corp|"
    r"moon\s+corp|space\s+banana|astro\s+banana)\b",
    re.IGNORECASE,
)

# ── Absurd numeric claim patterns ─────────────────────────────────────────────
# e.g. "999 years of experience", "5000%", "10000% increase"
_ABSURD_NUMBER_RE = re.compile(
    r"\b(\d{3,}\s*(?:years?|yrs?)\s+of\s+(?:experience|exp)\b"
    r"|(?:increase|growth|boost|improve)[^.]{0,30}[1-9]\d{3,}\s*%"
    r"|[1-9]\d{3,}\s*%\s+(?:increase|growth|boost|improve))",
    re.IGNORECASE,
)


def _text_has_scifi(text: str) -> list[str]:
    """Return matched sci-fi phrases found in text (lower-cased)."""
    lower = text.lower()
    return [phrase for phrase in _SCIFI_PHRASES if phrase in lower]


def _parse_year(date_str: str) -> int | None:
    """Extract the 4-digit year from a date string like '2024', '2024-06', '3020-01'."""
    if not date_str:
        return None
    m = re.match(r"(\d{4})", str(date_str).strip())
    return int(m.group(1)) if m else None


def check_profile_authenticity(profile_data: dict, owner_email: str = "", owner_name: str = "") -> dict:
    """
    Run all authenticity heuristics. Returns:
    {
        "flags": list[str],      # human-readable reasons for suspicion
        "penalty": int,          # total score deduction (0-50)
        "risk_level": str,       # "none" | "low" | "medium" | "high"
    }
    """
    flags: list[str] = []
    penalty = 0

    bio = (profile_data.get("bio") or "").strip()
    skills = profile_data.get("skills") or []
    experience = profile_data.get("experience") or []
    portfolio = profile_data.get("portfolio") or []
    title = (profile_data.get("title") or "").strip()

    # ── 1. Suspicious name ────────────────────────────────────────────────────
    if owner_name and _SUSPICIOUS_NAME_RE.match(owner_name.strip()):
        flags.append(f'Name "{owner_name}" looks like a test or dummy account.')
        penalty += 15

    # ── 2. Disposable email ───────────────────────────────────────────────────
    if owner_email and "@" in owner_email:
        domain = owner_email.split("@")[-1].lower()
        if domain in _DISPOSABLE_DOMAINS:
            flags.append(f"Email uses a known disposable email provider ({domain}).")
            penalty += 20

    # ── 3. Bio boilerplate ────────────────────────────────────────────────────
    if bio:
        bio_lower = bio.lower()
        matched_phrases = [p for p in _BOILERPLATE_PHRASES if p in bio_lower]
        if matched_phrases:
            flags.append(
                f"Bio contains boilerplate/generic phrases: {', '.join(repr(p) for p in matched_phrases[:3])}."
            )
            penalty += 15

        if len(bio.split()) < 15:
            flags.append("Bio is extremely short (fewer than 15 words).")
            penalty += 8

    # ── 4. Sci-fi / fantasy content detection ─────────────────────────────────
    # Check bio, title, and all experience + portfolio descriptions
    all_text_fields: list[tuple[str, str]] = [("bio", bio), ("title", title)]
    for exp in experience:
        desc = (exp.get("description") or "").strip()
        company = (exp.get("company") or "").strip()
        if desc:
            all_text_fields.append(("experience description", desc))
        if company:
            all_text_fields.append(("company name", company))
    for item in portfolio:
        desc = (item.get("description") or "").strip()
        if desc:
            all_text_fields.append(("portfolio description", desc))

    scifi_hits: list[str] = []
    for field_name, text in all_text_fields:
        matches = _text_has_scifi(text)
        if matches:
            scifi_hits.extend(matches[:2])

    if len(scifi_hits) >= 2:
        flags.append(
            f"Profile contains sci-fi/fantasy content that does not reflect real professional work "
            f"(detected: {', '.join(repr(h) for h in scifi_hits[:3])})."
        )
        penalty += 20
    elif len(scifi_hits) == 1:
        flags.append(
            f"Profile may contain fictional content: detected phrase '{scifi_hits[0]}'."
        )
        penalty += 10

    # ── 5. Fictional location ─────────────────────────────────────────────────
    location = (profile_data.get("location") or "").strip()
    if location and _FICTIONAL_LOCATION_RE.search(location):
        flags.append(
            f'Location "{location}" appears to be a fictional or non-existent place.'
        )
        penalty += 15

    # ── 6. Absurd title ───────────────────────────────────────────────────────
    if title and _ABSURD_TITLE_RE.search(title):
        flags.append(
            f'Professional title "{title}" contains non-professional or fictional keywords.'
        )
        penalty += 12

    # ── 7. Absurd numeric claims in bio or experience ─────────────────────────
    combined_text_for_numbers = bio + " " + " ".join(
        (e.get("description") or "") for e in experience
    )
    absurd_number_match = _ABSURD_NUMBER_RE.search(combined_text_for_numbers)
    if absurd_number_match:
        flags.append(
            f"Profile contains implausible numeric claims "
            f"(e.g. '{absurd_number_match.group(0)[:60]}')."
        )
        penalty += 15

    # ── 8. Far-future experience dates ────────────────────────────────────────
    for exp in experience:
        start = exp.get("start_date") or ""
        end = exp.get("end_date") or ""
        year_start = _parse_year(start)
        year_end = _parse_year(end)

        if year_start and year_start > _CURRENT_YEAR + 2:
            flags.append(
                f'Experience at "{exp.get("company", "unknown")}" has a start year far in the '
                f"future ({year_start}) — likely fictional or a data entry error."
            )
            penalty += 18

        elif year_start and year_start > _CURRENT_YEAR:
            flags.append(
                f'Experience at "{exp.get("company", "unknown")}" has a start date in the future ({start}).'
            )
            penalty += 8

        if year_end and year_end > _CURRENT_YEAR + 2:
            flags.append(
                f'Experience end date at "{exp.get("company", "unknown")}" is far in the future ({year_end}).'
            )
            penalty += 10

    # ── 9. Fictional company names ────────────────────────────────────────────
    fictional_companies: list[str] = []
    for exp in experience:
        company = (exp.get("company") or "").strip()
        if company and _FICTIONAL_COMPANY_RE.search(company):
            fictional_companies.append(company)
    if fictional_companies:
        flags.append(
            f"Experience lists fictional or implausible company names: "
            f"{', '.join(repr(c) for c in fictional_companies[:3])}."
        )
        penalty += 15

    # ── 10. Joke / non-professional skills ────────────────────────────────────
    joke_skills_found: list[str] = []
    for skill in skills:
        s_lower = skill.lower().strip()
        if any(joke in s_lower for joke in _JOKE_SKILL_WORDS):
            joke_skills_found.append(skill)

    if len(joke_skills_found) >= 2:
        flags.append(
            f"Skills list contains joke or non-professional entries: "
            f"{', '.join(repr(s) for s in joke_skills_found[:4])}."
        )
        penalty += 18
    elif len(joke_skills_found) == 1:
        flags.append(f"Skill '{joke_skills_found[0]}' does not appear to be a real professional skill.")
        penalty += 8

    # ── 11. Duplicate experience descriptions ─────────────────────────────────
    if len(experience) >= 2:
        descs = [e.get("description") or "" for e in experience if e.get("description")]
        for i in range(len(descs)):
            for j in range(i + 1, len(descs)):
                ratio = SequenceMatcher(None, descs[i].lower(), descs[j].lower()).ratio()
                if ratio > 0.85:
                    flags.append(
                        "Two experience entries have nearly identical descriptions — "
                        "copy-paste detected."
                    )
                    penalty += 12
                    break
            else:
                continue
            break

    # ── 12. All portfolio items point to same domain ──────────────────────────
    if len(portfolio) >= 2:
        from urllib.parse import urlparse
        domains = []
        for item in portfolio:
            url = item.get("url") or ""
            if url:
                try:
                    domains.append(urlparse(url).hostname or "")
                except Exception:
                    pass
        non_empty = [d for d in domains if d]
        if non_empty and len(set(non_empty)) == 1:
            flags.append(
                f"All portfolio links point to the same domain ({non_empty[0]}) — "
                "likely placeholder or copy-paste."
            )
            penalty += 12

    # ── 13. Portfolio identical descriptions ──────────────────────────────────
    if len(portfolio) >= 2:
        p_descs = [p.get("description") or "" for p in portfolio if p.get("description")]
        if len(p_descs) >= 2:
            ratio = SequenceMatcher(None, p_descs[0].lower(), p_descs[-1].lower()).ratio()
            if ratio > 0.85:
                flags.append("Portfolio item descriptions are nearly identical — copy-paste detected.")
                penalty += 12

    # ── 14. Unrealistically large or entirely generic skill list ──────────────
    if len(skills) > 25:
        flags.append(f"Skill list is unusually large ({len(skills)} skills) — may be inflated.")
        penalty += 8

    generic_skills = {
        "teamwork", "communication", "leadership", "problem solving",
        "microsoft office", "ms office", "word", "excel", "powerpoint",
        "management", "organization", "time management",
    }
    if skills:
        generic_count = sum(1 for s in skills if s.lower() in generic_skills)
        if generic_count / max(len(skills), 1) > 0.6:
            flags.append(
                "Most listed skills are generic non-technical skills with no specific technology skills."
            )
            penalty += 8

    # ── 15. Title ↔ skills domain mismatch (major flag) ───────────────────────
    if title and skills:
        tech_keywords = {
            "developer", "engineer", "programmer", "software", "backend", "frontend",
            "fullstack", "data", "ml", "ai", "devops", "cloud", "web", "mobile",
        }
        is_tech_title = any(kw in title.lower() for kw in tech_keywords)
        has_tech_skills = any(
            len(s) > 2 and s.lower() not in generic_skills for s in skills
        )
        if is_tech_title and not has_tech_skills:
            flags.append(
                f'Profile title is "{title}" (technical) but skills are all non-technical.'
            )
            penalty += 15

    # ── 16. Completely empty profile ──────────────────────────────────────────
    if not bio and not skills and not experience and not portfolio:
        flags.append("Profile is completely empty — no bio, skills, experience, or portfolio.")
        penalty += 10

    penalty = min(penalty, 60)
    if penalty == 0:
        risk_level = "none"
    elif penalty <= 10:
        risk_level = "low"
    elif penalty <= 28:
        risk_level = "medium"
    else:
        risk_level = "high"

    return {"flags": flags, "penalty": penalty, "risk_level": risk_level}


def compute_url_warnings(portfolio: list[dict], proof_signals: list[dict]) -> list[str]:
    """
    Synchronous heuristic URL warnings (format-only, not HTTP).
    Async reachability checks happen in credibility_service.
    """
    warnings: list[str] = []
    from urllib.parse import urlparse

    all_urls = []
    for item in portfolio:
        u = item.get("url") or ""
        if u:
            all_urls.append(("portfolio", item.get("title", "item"), u))

    for sig in proof_signals:
        u = sig.get("url") or ""
        if u:
            all_urls.append(("signal", sig.get("title", "signal"), u))

    seen: set[str] = set()
    for category, label, url in all_urls:
        if url in seen:
            warnings.append(f'Duplicate URL detected: "{url}" appears more than once.')
        seen.add(url)

        try:
            parsed = urlparse(url)
            host = parsed.hostname or ""
            path = parsed.path or ""
            if path in ("", "/") and host.count(".") == 1:
                pass
        except Exception:
            warnings.append(f'Malformed URL in {category} "{label}".')

    return warnings
