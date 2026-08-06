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
    m = re.search(r"\b(19\d{2}|20[0-2]\d)\s*-\s*(?:R|PG|G|NR|Not Rated|PG-13)", row_text)
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


def _verify_page(html: str, theater_key: str, date: dt.date) -> None:
    """Refuse to parse a page that isn't the one we asked for."""
    want_date = f"{WEEKDAYS[date.weekday()]}, {MONTHS[date.month - 1]} {date.day}, {date.year}"
    if f"Showtimes on {want_date}" not in html:
        raise RuntimeError(
            f"{theater_key}: page is not {want_date} — got redirected or served a cache. "
            f"Nothing parsed."
        )


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
        if len(cells) < 2:
            continue
        text = tr.get_text(" ", strip=True)

        # The title is the anchor pointing at a NowShowing movie page.
        link = tr.find("a", href=re.compile(r"NowShowing\.php\?movie="))
        if not link:
            continue
        title = link.get_text(strip=True)
        if not title or title.lower() == "movie poster":
            continue

        # Showtimes live in the last cell, comma separated, followed by
        # the format label.
        times_cell = cells[-1].get_text(" ", strip=True)
        fmt = _detect_format(times_cell)
        stripped = re.split(r"(?i)(digital|70mm|35mm|imax|dolby|3d)\s*projection", times_cell)[0]

        for token in stripped.split(","):
            t = _parse_time(token, date)
            if not t:
                continue
            rows.append({
                "theater": theater_key,
                "title": title,
                "year": _year(text),
                "starts_at": t.isoformat(timespec="minutes"),
                "format": fmt,
                "runtime_hint": _runtime(text),
                "note": "",
                "ticket_url": "",
                "source_url": url,
            })

    return rows


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
