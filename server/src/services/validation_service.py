"""
Authenticity validation for all profile data.
Called from routers before writing anything to the database.
"""
import io
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# ── Blocked URL domains ───────────────────────────────────────────────────────

_BLOCKED_DOMAINS = {
    "example.com", "example.org", "example.net",
    "test.com", "test.org", "test.net",
    "placeholder.com", "yoursite.com", "mywebsite.com",
    "website.com", "domain.com", "sample.com",
    "foo.bar", "tempurl.com", "dummysite.com",
    "fakesite.com", "abc.com", "xyz.com",
    "localhost", "127.0.0.1", "0.0.0.0",
}

# ── Placeholder phrases ───────────────────────────────────────────────────────

_PLACEHOLDER_BIO = [
    "lorem ipsum", "write your bio here", "about me section",
    "experienced professional", "i am a professional", "insert bio",
    "your bio here", "add your description", "click to edit",
]

_PLACEHOLDER_CV = [
    "your name here", "lorem ipsum", "insert experience",
    "sample resume", "your address here", "enter your",
    "add your", "click to edit", "write your bio",
]


@dataclass
class ValidationError:
    field: str
    message: str


# ── URL validation ────────────────────────────────────────────────────────────

def validate_url(url: str, field: str = "url") -> ValidationError | None:
    if not url:
        return None
    url = url.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        return ValidationError(field, "URL must start with http:// or https://")
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        host = parsed.hostname or ""
        host = host.lower()
        for blocked in _BLOCKED_DOMAINS:
            if host == blocked or host.endswith("." + blocked):
                return ValidationError(
                    field,
                    f'"{host}" is not a real URL. Please use your actual project or profile link.',
                )
    except Exception:
        return ValidationError(field, "Invalid URL format.")
    return None


# ── Bio validation ────────────────────────────────────────────────────────────

def validate_bio(bio: str) -> ValidationError | None:
    if not bio:
        return None
    trimmed = bio.strip()
    if len(trimmed) < 80:
        return ValidationError("bio", f"Bio must be at least 80 characters (currently {len(trimmed)}).")
    lower = trimmed.lower()
    for phrase in _PLACEHOLDER_BIO:
        if phrase in lower:
            return ValidationError(
                "bio",
                f'Bio contains placeholder text ("{phrase}"). Please write about your real background.',
            )
    return None


# ── Experience validation ─────────────────────────────────────────────────────

def _normalize_date(s: str) -> str:
    """Normalize 'YYYY-M' to 'YYYY-MM' so lexicographic comparison is correct.
    Without this, '2024-9' > '2024-10' (September appears after October), which is wrong.
    """
    if not s:
        return s
    parts = s.split('-')
    if len(parts) == 2:
        year, month = parts
        return f"{year}-{month.zfill(2)}"
    return s


def validate_experience_list(entries: list[dict]) -> list[ValidationError]:
    errors: list[ValidationError] = []
    for i, entry in enumerate(entries):
        desc = (entry.get("description") or "").strip()
        if desc and len(desc) < 40:
            errors.append(ValidationError(
                f"experience[{i}].description",
                "Experience description must be at least 40 characters or left empty.",
            ))

        company = (entry.get("company") or "").strip().lower()
        start = _normalize_date(entry.get("start_date") or "")
        end = "9999-99" if entry.get("current") else _normalize_date(entry.get("end_date") or "9999-99")

        for j, other in enumerate(entries):
            if j >= i:
                continue
            other_company = (other.get("company") or "").strip().lower()
            if other_company and other_company == company:
                o_start = _normalize_date(other.get("start_date") or "")
                o_end = "9999-99" if other.get("current") else _normalize_date(other.get("end_date") or "9999-99")
                if start <= o_end and o_start <= end:
                    errors.append(ValidationError(
                        f"experience[{i}]",
                        f'Duplicate experience: overlapping entry for "{entry.get("company")}" already exists.',
                    ))
                    break
    return errors


# ── Portfolio URL validation ──────────────────────────────────────────────────

def validate_portfolio_list(items: list[dict]) -> list[ValidationError]:
    errors: list[ValidationError] = []
    seen_urls: set[str] = set()
    for i, item in enumerate(items):
        url = (item.get("url") or "").strip()
        if url:
            err = validate_url(url, f"portfolio[{i}].url")
            if err:
                errors.append(err)
            elif url in seen_urls:
                errors.append(ValidationError(f"portfolio[{i}].url", "This portfolio URL is already listed."))
            else:
                seen_urls.add(url)
    return errors


# ── Image content validation ──────────────────────────────────────────────────

def validate_image_content(file_bytes: bytes) -> ValidationError | None:
    """Reject blank/solid-color placeholder images."""
    try:
        from PIL import Image
        import struct

        img = Image.open(io.BytesIO(file_bytes))
        w, h = img.size

        if w < 100 or h < 100:
            return ValidationError("file", "Image is too small (minimum 100×100 pixels). Please upload a real screenshot.")

        # Convert to grayscale and check pixel variance
        gray = img.convert("L")
        pixels = list(gray.getdata())
        if not pixels:
            return ValidationError("file", "Could not read image content.")

        mean = sum(pixels) / len(pixels)
        variance = sum((p - mean) ** 2 for p in pixels) / len(pixels)

        if variance < 50:
            return ValidationError(
                "file",
                "The image appears to be a solid colour or blank placeholder. Please upload a real work screenshot.",
            )
        return None
    except Exception as exc:
        logger.debug("Image validation skipped: %s", exc)
        return None  # Don't block if PIL fails — just skip validation


# ── CV content validation ─────────────────────────────────────────────────────

def validate_cv_text(text: str) -> ValidationError | None:
    words = text.split()
    if len(words) < 80:
        return ValidationError("cv", f"CV has too little content ({len(words)} words). Minimum 80 words required.")
    lower = text.lower()
    for phrase in _PLACEHOLDER_CV:
        if phrase in lower:
            return ValidationError("cv", f'CV appears to be a template (detected: "{phrase}").')
    return None


# ── Full profile validation ───────────────────────────────────────────────────

def validate_full_profile(data: dict) -> list[ValidationError]:
    """
    Run all authenticity checks on profile data dict.
    Returns a list of ValidationError (empty = all good).
    """
    errors: list[ValidationError] = []

    bio_err = validate_bio(data.get("bio") or "")
    if bio_err:
        errors.append(bio_err)

    errors.extend(validate_experience_list(data.get("experience") or []))
    errors.extend(validate_portfolio_list(data.get("portfolio") or []))

    return errors
