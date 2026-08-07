"""Turning a rendered calendar page into rows.

Two ways to do this:

  1. extract_llm()  — hand the page text to Claude, get JSON back.
     Survives redesigns. Costs a fraction of a cent per page.
  2. Hand-written BeautifulSoup selectors per theater.
     Free forever, breaks whenever a theater redesigns.

Either way, everything goes through validate() before it counts.
Nothing reaches your dashboard that isn't literally on the page.
"""

import json, os, re, datetime as dt
import requests

SCHEMA_PROMPT = """Extract every film screening from this cinema calendar page.

Return ONLY a JSON array, no markdown fences, no commentary. One object per
individual showtime:

{"title": "", "year": null, "starts_at": "YYYY-MM-DDTHH:MM",
 "format": "imax|dolby|70mm|35mm|3d|4k|standard", "note": "", "ticket_url": ""}

Rules:
- One object per showtime, NOT per film. A film with four showings on the
  page produces four objects.
- starts_at must use 24-hour time. A midnight show on Saturday belongs to
  Saturday's date at 24:00 in the theater's own listing convention, so write
  it as the following day at 00:00.
- format: only if the page names a print or presentation format.
- note: keep anything a plain listing would lose — "director in person",
  "35mm print", "part of the Varda retrospective", "midnight movie".
  Empty string if there's nothing.
- year: the film's release year if the page states it. Never guess it.
- Use ONLY what is written on the page. If a date or time is ambiguous,
  OMIT that screening. Never infer, complete, or invent a showtime.
  A missing screening is fine. A wrong one is not.
"""


def extract_llm(text: str, url: str, model: str = "claude-sonnet-4-6") -> list[dict]:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not set — use hand-written selectors instead")

    body = {
        "model": model,
        "max_tokens": 8000,
        "messages": [{"role": "user",
                      "content": f"{SCHEMA_PROMPT}\n\nPAGE URL: {url}\n\nTODAY: {dt.date.today()}\n\nPAGE TEXT:\n{text[:120000]}"}],
    }
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"},
        json=body, timeout=120,
    )
    r.raise_for_status()
    raw = "".join(c.get("text", "") for c in r.json()["content"])
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
    return json.loads(raw)


# --------------------------------------------------------------------
# Validation — the part that matters more than the extraction
# --------------------------------------------------------------------

TIME_PATTERNS = [
    "%-I:%M%p", "%-I:%M %p", "%-I:%M", "%H:%M",
]


def time_strings(t: dt.datetime) -> list[str]:
    """Every plausible way a cinema might print this time."""
    h12 = t.hour % 12 or 12
    return [
        f"{h12}:{t.minute:02d}",
        f"{h12}:{t.minute:02d}pm", f"{h12}:{t.minute:02d} pm",
        f"{h12}:{t.minute:02d}PM", f"{h12}:{t.minute:02d} PM",
        f"{h12}:{t.minute:02d}am", f"{h12}:{t.minute:02d} am",
        f"{t.hour:02d}:{t.minute:02d}",
    ]


def validate(rows: list[dict], page_text: str, window_days: int = 21) -> tuple[list[dict], list[str]]:
    """Drop anything we can't corroborate against the page itself."""
    kept, rejected = [], []
    flat = re.sub(r"\s+", " ", page_text.lower())
    today = dt.date.today()

    for row in rows:
        title = (row.get("title") or "").strip()
        if not title:
            rejected.append("row with no title")
            continue
        try:
            t = dt.datetime.fromisoformat(row["starts_at"])
        except Exception:
            rejected.append(f"{title}: unparseable time {row.get('starts_at')!r}")
            continue

        if not (today - dt.timedelta(1) <= t.date() <= today + dt.timedelta(window_days)):
            rejected.append(f"{title}: {t.date()} outside the scrape window")
            continue
        if 3 <= t.hour < 10:
            rejected.append(f"{title}: {t:%H:%M} is not a plausible showtime")
            continue
        if not any(s.lower() in flat for s in time_strings(t)):
            rejected.append(f"{title}: {t:%H:%M} does not appear on the page")
            continue
        if title.lower() not in flat:
            rejected.append(f"{title}: title does not appear on the page")
            continue

        kept.append(row)

    return kept, rejected
