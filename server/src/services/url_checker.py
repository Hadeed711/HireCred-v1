"""
Async URL reachability checker with page-title extraction.
Makes a HEAD request (falls back to GET) with a short timeout.
For non-trusted domains, also fetches page content to extract the <title> tag —
this catches URLs that are syntactically valid but lead nowhere (parked domains,
404 pages, placeholder pages).
Results are cached for 60 seconds.
"""
import re
import time
import logging
import httpx

logger = logging.getLogger(__name__)

_cache: dict[str, tuple[dict, float]] = {}
_CACHE_TTL = 60.0
_TIMEOUT = 4.0
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)

# Domains we trust to exist but skip HTTP check (to avoid bans / rate-limits)
_SKIP_CHECK_DOMAINS = {
    "github.com", "linkedin.com", "twitter.com", "x.com",
    "behance.net", "dribbble.com", "medium.com", "dev.to",
    "stackoverflow.com", "npmjs.com", "pypi.org",
}

# Title text that indicates a parked / dead / placeholder page
_DEAD_PAGE_TITLES = {
    "domain for sale", "buy this domain", "parked domain", "index of /",
    "403 forbidden", "404 not found", "page not found", "error 404",
    "coming soon", "under construction", "placeholder page",
    "default web page", "welcome to nginx", "apache2 default page",
    "it works!", "website coming soon", "this site can't be reached",
    "account suspended", "web hosting", "domain expired",
}


def _extract_title(html: str) -> str | None:
    m = _TITLE_RE.search(html[:8000])
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip()
    return None


def _is_dead_title(title: str | None) -> bool:
    if not title:
        return False
    low = title.lower()
    return any(phrase in low for phrase in _DEAD_PAGE_TITLES)


async def check_url(url: str) -> dict:
    """
    Returns:
      reachable: bool
      status_code: int | None
      note: str — human-readable explanation
      page_title: str | None — extracted <title> tag if fetched
      title_suspicious: bool — True if title looks like a dead/placeholder page
    """
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        return {
            "reachable": False, "status_code": None,
            "note": "URL must start with http:// or https://",
            "page_title": None, "title_suspicious": False,
        }

    # Cache hit
    if url in _cache:
        result, ts = _cache[url]
        if time.time() - ts < _CACHE_TTL:
            return result

    # Well-known trusted domains — skip check
    try:
        from urllib.parse import urlparse
        host = urlparse(url).hostname or ""
        for trusted in _SKIP_CHECK_DOMAINS:
            if host == trusted or host.endswith("." + trusted):
                result = {
                    "reachable": True, "status_code": 200,
                    "note": "Trusted domain — not checked",
                    "page_title": None, "title_suspicious": False,
                }
                _cache[url] = (result, time.time())
                return result
    except Exception:
        pass

    headers = {"User-Agent": "HireCred-Validator/1.0"}
    page_title: str | None = None
    title_suspicious = False

    async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True, verify=True, max_redirects=10) as client:
        # HEAD first (fast)
        try:
            resp = await client.head(url, headers=headers)
            code = resp.status_code
            reachable = code < 400
            if reachable:
                # Fetch a snippet of the page to get the title
                try:
                    get_resp = await client.get(url, headers=headers)
                    raw = get_resp.text[:10000]
                    page_title = _extract_title(raw)
                    title_suspicious = _is_dead_title(page_title)
                    if title_suspicious:
                        note = f"Page title suggests a dead or parked page: \"{page_title}\""
                    else:
                        note = f"OK (title: {page_title})" if page_title else "OK"
                except Exception:
                    note = "OK" if reachable else f"Server returned {code}"
            else:
                note = f"Server returned {code}"
            result = {
                "reachable": reachable and not title_suspicious,
                "status_code": code, "note": note,
                "page_title": page_title, "title_suspicious": title_suspicious,
            }
            _cache[url] = (result, time.time())
            return result
        except Exception:
            pass

        # HEAD failed — try GET with streaming
        try:
            async with client.stream("GET", url, headers=headers) as resp:
                code = resp.status_code
                reachable = code < 400
                # Read first chunk for title
                try:
                    chunk = b""
                    async for c in resp.aiter_bytes(chunk_size=8192):
                        chunk += c
                        if len(chunk) >= 8192:
                            break
                    page_title = _extract_title(chunk.decode("utf-8", errors="ignore"))
                    title_suspicious = _is_dead_title(page_title)
                except Exception:
                    pass
                if title_suspicious:
                    note = f"Page title suggests a dead or parked page: \"{page_title}\""
                elif reachable:
                    note = f"OK (title: {page_title})" if page_title else "OK"
                else:
                    note = f"Server returned {code}"
                result = {
                    "reachable": reachable and not title_suspicious,
                    "status_code": code, "note": note,
                    "page_title": page_title, "title_suspicious": title_suspicious,
                }
                _cache[url] = (result, time.time())
                return result
        except httpx.ConnectError:
            result = {
                "reachable": False, "status_code": None,
                "note": "Could not connect — domain may not exist",
                "page_title": None, "title_suspicious": False,
            }
        except httpx.ConnectTimeout:
            result = {
                "reachable": False, "status_code": None,
                "note": "Connection timed out",
                "page_title": None, "title_suspicious": False,
            }
        except httpx.RemoteProtocolError:
            result = {
                "reachable": False, "status_code": None,
                "note": "SSL or protocol error — certificate may be invalid",
                "page_title": None, "title_suspicious": False,
            }
        except httpx.TimeoutException:
            result = {
                "reachable": False, "status_code": None,
                "note": "Request timed out — site may be down",
                "page_title": None, "title_suspicious": False,
            }
        except Exception as exc:
            result = {
                "reachable": False, "status_code": None,
                "note": f"Check failed: {type(exc).__name__}",
                "page_title": None, "title_suspicious": False,
            }

    _cache[url] = (result, time.time())
    return result
