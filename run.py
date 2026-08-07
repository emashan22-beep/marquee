"""All five theaters from one source.

The BigScreen Cinema Guide lists every Chicago theater on identical
plain-HTML pages with a ?showdate= parameter. No JavaScript, no API key,
no per-theater parser. One scraper covers the whole slate.

Why this rather than the theaters' own sites:
  - Music Box's robots.txt disallows /calendar. Scraping it anyway would
    be rude and we don't need to.
  - AMC's vendor API needs approval that may never come for a personal
    project.
  - Three bespoke parsers is three things to maintain.

The trade-off: it's a middleman, so it can be stale or thin, and it may
miss a theater's series framing ("Technicolor Weekend"). Use the AMC API
for the AMCs if your vendor key comes through, and treat Siskel's own
Agile Ticketing calendar as the better source for series names.
"""

import re
import datetime as dt
from bs4 import BeautifulSoup
from . import web

BASE = "https://www.bigscreen.com/Marquee.php"

# Found via the "theaters near 60613" page. These are stable.
THEATER_IDS = {
    "musicbox":  940,
    "logan":     932,
    "siskel":    937,
    "newcity":   42492,   # AMC NEWCITY 14
    "rivereast": 8267,    # AMC River East 21
}

# How BigScreen labels presentation formats.
FORMAT_WORDS = [
    ("70mm projection", "70mm"),
    ("35mm projection", "35mm"),
    ("imax", "imax"),
    ("dolby cinema", "dolby"),
    ("3d", "3d"),
    ("digital projection", "standard"),
]


def url_for(theater_key: str, date: dt.date) -> str:
    return (f"{BASE}?theater={THEATER_IDS[theater_key]}&view=sched"
            f"&showdate={date:%Y-%m-%d}&sort=date")


def _parse_time(token: str, date: dt.date) -> dt.datetime | None:
    """'2:15' / '11:15a' / '11:59' -> a datetime.

    BigScreen writes afternoon and evening times bare and marks morning
    times with a trailing 'a'. 11:59 with no marker is the midnight show.
    """
    token = token.strip().lower().rstrip(",")
    m = re.match(r"^(\d{1,2}):(\d{2})\s*(a|p)?m?$", token)
    if not m:
        return None
    hour, minute, ampm = int(m.group(1)), int(m.group(2)), m.group(3)
    if ampm == "a":
        if hour == 12:
            hour = 0
    elif ampm == "p":
        if hour != 12:
            hour += 12
    else:
        # No marker: cinemas run noon to midnight, so 1-11 means PM.
        if 1 <= hour <= 11:
            hour += 12
    return dt.datetime.combine(date, dt.time(hour, minute))


def _detect_format(cell_text: str) -> str:
    low = cell_text.lower()
    for needle, fmt in FORMAT_WORDS:
        if needle in low:
            return fmt
    return "standard"


def _runtime(row_text: str) -> int:
    m = re.search(r"running time:\s*(\d+):(\d{2})", row_text, re.I)
    return int(m.group(1)) * 60 + int(m.group(2)) if m else 0


def _year(row_text: str) -> int | None:
    m = re.search(r"\b(19\d{2}|20[0-2]\d)\s*[-–]\s*", row_text)
    return int(m.group(1)) if m else None


_warmed: set[str] = set()

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]


def _warm_up(theater_key: str) -> None:
    """Load the theater's base page once so the session cookie is set.

    Without this, a dated request gets silently redirected to the
    'theaters near you' directory and you parse zero showtimes — which
    looks exactly like a theater that is closed.
    """
    if theater_key in _warmed:
        return
    web.fetch_plain(f"{BASE}?theater={THEATER_IDS[theater_key]}")
    _warmed.add(theater_key)


def _plain(html: str) -> str:
    """Tag-free, whitespace-collapsed text. Markup inside a heading must
    not defeat the date check."""
    txt = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    txt = re.sub(r"\s+", " ", txt)
    # "Friday </b>, August" -> "Friday, August"
    return re.sub(r"\s+([,.])", r"\1", txt)


def page_date_ok(html: str, date: dt.date) -> bool:
    want = f"{WEEKDAYS[date.weekday()]}, {MONTHS[date.month - 1]} {date.day}, {date.year}"
    return f"Showtimes on {want}" in _plain(html)


def _verify_page(html: str, theater_key: str, date: dt.date) -> None:
    """Refuse to parse a page that isn't the one we asked for."""
    if page_date_ok(html, date):
        return
    text = _plain(html)
    hint = "looks like the theater directory" if "Theaters Found" in text else "unknown page"
    found = re.search(r"Showtimes on ([A-Z][a-z]+, [A-Z][a-z]+ \d{1,2}, \d{4})", text)
    raise RuntimeError(
        f"{theater_key}: wanted {date:%A, %B %-d, %Y} but got "
        f"{found.group(1) if found else hint} ({len(html):,} bytes). "
        f"Session cookie probably not set."
    )


TIME_RE = re.compile(r"\b\d{1,2}:\d{2}\s*[ap]?\.?m?\.?\b", re.I)
JUNK_LINKS = {"movie poster", "poster", "photos", "videos", "reviews", "media",
              "more", "showtimes", "read more"}


def _title_from_anchor(a) -> str:
    """The visible text, or the link's title attribute as a fallback.

    The poster link in each row wraps an <img> and so has NO text at all —
    get_text() returns "". Taking the first matching anchor therefore
    yielded an empty title and silently skipped every row. Its title
    attribute reads "View showtimes and information for <FILM>", which is
    a perfectly good source.
    """
    txt = a.get_text(" ", strip=True)
    if txt and txt.lower() not in JUNK_LINKS:
        return txt
    attr = a.get("title") or ""
    m = re.search(r"(?:information|reviews)\s+for\s+(.+?)\s*$", attr)
    if m:
        return m.group(1).strip()
    return ""


def _row_title(tr) -> str:
    best = ""
    for a in tr.find_all("a", href=re.compile(r"NowShowing\.php\?movie=")):
        t = _title_from_anchor(a)
        if len(t) > len(best):
            best = t
    return best


def _times_cell(cells) -> str:
    """The cell holding the showtimes, found by shape rather than position."""
    for c in reversed(cells):
        t = c.get_text(" ", strip=True)
        if TIME_RE.search(t):
            return t
    return ""


def scrape(theater_key: str, date: dt.date) -> list[dict]:
    _warm_up(theater_key)
    url = url_for(theater_key, date)
    html = web.fetch_plain(url)
    if web.looks_blocked(html):
        raise RuntimeError(f"{theater_key}: blocked at {url}")
    _verify_page(html, theater_key, date)

    soup = BeautifulSoup(html, "html.parser")
    rows = []

    for tr in soup.select("tr"):
        cells = tr.find_all("td")
        if not cells:
            continue

        title = _row_title(tr)
        if not title:
            continue

        times_text = _times_cell(cells)
        if not times_text:
            continue

        row_text = tr.get_text(" ", strip=True)
        fmt = _detect_format(times_text)
        # everything before the "... Projection" label is the time list
        stripped = re.split(r"(?i)(digital|70\s?mm|35\s?mm|imax|dolby|3-?d|real\s?d)[a-z ]*projection",
                            times_text)[0]

        for token in re.split(r"[,/]", stripped):
            t = _parse_time(token, date)
            if not t:
                continue
            rows.append({
                "theater": theater_key,
                "title": title,
                "year": _year(row_text),
                "starts_at": t.isoformat(timespec="minutes"),
                "format": fmt,
                "runtime_hint": _runtime(row_text),
                "note": "",
                "ticket_url": "",
                "source_url": url,
            })

    return rows


def probe(theater_key: str, date: dt.date) -> dict:
    """Fetch one page and report what came back, without parsing.

    This is what to run when a scrape fails: it tells you whether you got
    the right page at all before you start blaming the parser.
    """
    _warm_up(theater_key)
    url = url_for(theater_key, date)
    html = web.fetch_plain(url)
    text = _plain(html)
    found = re.search(r"Showtimes on ([A-Z][a-z]+, [A-Z][a-z]+ \d{1,2}, \d{4})", text)
    rows = []
    if page_date_ok(html, date):
        try:
            rows = scrape(theater_key, date)
        except Exception as e:
            rows = [{"error": str(e)}]
    return {
        "url": url,
        "bytes": len(html),
        "blocked": web.looks_blocked(html),
        "is_directory": "Theaters Found" in text,
        "page_says": found.group(1) if found else None,
        "date_ok": page_date_ok(html, date),
        "rows_parsed": len(rows),
        "movie_links": len(BeautifulSoup(html, "html.parser")
                          .find_all("a", href=re.compile(r"NowShowing\.php\?movie="))),
        "table_rows": len(BeautifulSoup(html, "html.parser").select("tr")),
        "sample": [f"{r.get('starts_at')} {r.get('format')} {r.get('title')}" for r in rows[:5]],
        "text_head": text[:400],
    }


def scrape_weekend(theater_key: str, days: list[dt.date]) -> list[dict]:
    out = []
    for d in days:
        out += scrape(theater_key, d)
    return out


if __name__ == "__main__":
    # python -m pipeline.sources.bigscreen  — quick smoke test
    import sys
    key = sys.argv[1] if len(sys.argv) > 1 else "musicbox"
    day = dt.date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else dt.date.today()
    for r in scrape(key, day):
        print(f"{r['starts_at']}  {r['format']:<9} {r['title']}")
