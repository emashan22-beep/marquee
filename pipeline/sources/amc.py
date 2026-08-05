"""AMC River East 21 and New City 14, via AMC's official free API.

Get a vendor key: developers.amctheatres.com/GettingStarted/NewVendorRequest
Then find your theatre IDs through their Location or Theatre API.
"""

import os, datetime as dt
import requests

BASE = "https://api.amctheatres.com"


def _headers():
    key = os.environ.get("AMC_KEY")
    if not key:
        raise RuntimeError("AMC_KEY not set")
    return {"X-AMC-Vendor-Key": key}


def find_theatres(query: str = "Chicago") -> list[dict]:
    """Run this once to discover your two theatre IDs, then hardcode them
    in config.AMC_THEATRE_IDS."""
    r = requests.get(f"{BASE}/v2/theatres", headers=_headers(),
                     params={"page-size": 100}, timeout=30)
    r.raise_for_status()
    out = []
    for t in r.json().get("_embedded", {}).get("theatres", []):
        if query.lower() in (t.get("location", {}).get("city", "") or "").lower():
            out.append({"id": t.get("id"), "name": t.get("name"),
                        "address": t.get("location", {}).get("addressLine1")})
    return out


def showtimes(theatre_id: int, date: dt.date) -> list[dict]:
    url = f"{BASE}/v2/theatres/{theatre_id}/showtimes/{date:%m-%d-%y}"
    rows, page = [], 1
    while True:
        r = requests.get(url, headers=_headers(),
                         params={"page-number": page, "page-size": 100}, timeout=30)
        r.raise_for_status()
        body = r.json()
        rows += body.get("_embedded", {}).get("showtimes", [])
        if page * body.get("pageSize", 100) >= body.get("count", 0):
            break
        page += 1
    return rows


# AMC exposes presentation as structured attributes rather than strings
# buried in the auditorium name. Map them explicitly and log misses.
ATTR_FORMAT = {
    "imax": "imax", "imaxwithlaser": "imax", "imax70mm": "70mm",
    "dolbycinemaatamcprime": "dolby", "dolbycinema": "dolby",
    "realdthreed": "3d", "threed": "3d", "digitalthree_d": "3d",
    "seventymm": "70mm", "thirtyfivemm": "35mm",
}

_unmapped = set()


def to_rows(raw: list[dict], theater_key: str) -> list[dict]:
    out = []
    for s in raw:
        attrs = [a.get("code", "").lower().replace(" ", "")
                 for a in (s.get("attributes") or [])]
        fmt = "standard"
        for a in attrs:
            if a in ATTR_FORMAT:
                fmt = ATTR_FORMAT[a]
                break
            if a and a not in ("closedcaption", "reserveseating", "openCaption".lower(),
                               "descriptivevideo", "assistivelistening", "recliners"):
                _unmapped.add(a)
        out.append({
            "theater": theater_key,
            "title": s.get("movieName"),
            "year": None,
            "starts_at": (s.get("showDateTimeLocal") or "")[:16],
            "format": fmt,
            "note": "",
            "ticket_url": (s.get("_links", {}).get("purchaseTicket", {}) or {}).get("href", ""),
            "source_url": f"{BASE}/v2/theatres/{s.get('theatreId')}/showtimes",
        })
    return out


def unmapped_attributes() -> set:
    """Check this after a run. A new premium format showing up here is
    worth adding to ATTR_FORMAT rather than letting it read as standard."""
    return _unmapped
