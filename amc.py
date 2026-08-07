"""Fetching pages. Plain HTTP where possible, a browser where required."""

import re
import requests
from bs4 import BeautifulSoup

UA = "marquee-personal/1.0 (personal weekend dashboard; contact: you@example.com)"
HEADERS = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}


_SESSION = None


def session() -> requests.Session:
    """One cookie jar for the whole run.

    Some listing sites drop a ?theater= parameter entirely unless a
    session cookie is already set, and silently redirect you to their
    directory page instead. A shared Session fixes that.
    """
    global _SESSION
    if _SESSION is None:
        _SESSION = requests.Session()
        _SESSION.headers.update(HEADERS)
    return _SESSION


def fetch_plain(url: str, timeout: int = 25) -> str:
    r = session().get(url, timeout=timeout)
    r.raise_for_status()
    return r.text


def fetch_rendered(url: str, wait_selector: str | None = None, timeout: int = 30000) -> str:
    """For sites behind a JavaScript check. Slower, still free.

    Optional: only needed if you add a source that requires a browser.
    pip install playwright && playwright install chromium
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError(
            "this source needs a browser: pip install playwright "
            "&& playwright install chromium"
        )

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(user_agent=UA)
        try:
            page.goto(url, wait_until="networkidle", timeout=timeout)
            if wait_selector:
                page.wait_for_selector(wait_selector, timeout=timeout)
            page.wait_for_timeout(1500)   # let late JS settle
            return page.content()
        finally:
            browser.close()


def looks_blocked(html: str) -> bool:
    """Catches the 'enable javascript' interstitials so you get a clear
    error instead of an empty result."""
    low = html.lower()
    if len(low) < 2000 and "javascript" in low:
        return True
    return any(s in low for s in [
        "please enable javascript", "you are being redirected",
        "checking your browser", "captcha", "access denied",
    ])


def fetch(url: str, use_browser: bool = False, wait_selector: str | None = None) -> str:
    if use_browser:
        return fetch_rendered(url, wait_selector)
    html = fetch_plain(url)
    if looks_blocked(html):
        # Fall back rather than silently returning a challenge page.
        return fetch_rendered(url, wait_selector)
    return html


def page_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return re.sub(r"\n{3,}", "\n\n", soup.get_text("\n", strip=True))


def page_links(html: str, base: str = "") -> list[str]:
    from urllib.parse import urljoin
    soup = BeautifulSoup(html, "html.parser")
    out, seen = [], set()
    for a in soup.find_all("a", href=True):
        u = urljoin(base, a["href"])
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def og_image(html: str, base: str = "") -> str | None:
    """The poster or key art a page advertises to social media.

    This is how you get artwork for the things TMDB has never heard of:
    festival programmes, midnight series, one-off live events.
    """
    from urllib.parse import urljoin
    soup = BeautifulSoup(html, "html.parser")
    for sel, attr in [
        ('meta[property="og:image"]', "content"),
        ('meta[name="twitter:image"]', "content"),
        ('link[rel="image_src"]', "href"),
    ]:
        tag = soup.select_one(sel)
        if tag and tag.get(attr):
            return urljoin(base, tag[attr])
    return None
