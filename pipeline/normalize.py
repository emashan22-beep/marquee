"""Rows from five different sources -> one deduplicated slate.

This is the file that makes the comparison ruler work: the same film at
three theaters must become ONE film with three sets of showings, not
three films.
"""

import re, unicodedata, datetime as dt
from config import FORMATS, NOTE_CUES

DAY_ID = {4: "fri", 5: "sat", 6: "sun"}


def norm_title(t: str) -> str:
    """Aggressive normalisation for matching only. Never displayed."""
    t = unicodedata.normalize("NFKD", (t or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"\(?\b(4k|imax|70\s?mm|35\s?mm|3d|dolby|restoration|restored|"
               r"re-?release|re-?issue|director'?s cut|extended cut|anniversary|"
               r"presented in .*|in \d{2,3}mm)\b\)?", " ", t)
    t = re.sub(r"\b(the|a|an|le|la|les|el|il)\b", " ", t)
    return re.sub(r"[^a-z0-9]", "", t)


def slug(title: str, year) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", (title or "").lower()).strip("-")[:48]
    return f"{base}-{year}" if year else base


def detect_format(text: str) -> str:
    low = (text or "").lower()
    for needle, fmt in sorted(FORMATS.items(), key=lambda kv: -len(kv[0])):
        if needle in low:
            return fmt
    return "standard"


def extract_note(text: str) -> str:
    low = (text or "").lower()
    return "; ".join(c for c in NOTE_CUES if c in low)


def build_slate(rows: list[dict], weekend: list[dt.date], meta: dict | None = None) -> list[dict]:
    """rows: flat showings. weekend: [fri, sat, sun]. meta: film_key -> TMDB data."""
    meta = meta or {}
    want = {d.isoformat(): DAY_ID[d.weekday()] for d in weekend}
    films: dict[str, dict] = {}

    for r in rows:
        try:
            t = dt.datetime.fromisoformat(r["starts_at"])
        except Exception:
            continue

        # A midnight or 1am show belongs to the previous evening's programme.
        listing_date = t.date()
        hour = t.hour
        if hour < 4:
            listing_date -= dt.timedelta(1)
            hour += 24
        day = want.get(listing_date.isoformat())
        if not day:
            continue  # not this weekend

        key = norm_title(r["title"])
        if not key:
            continue
        m = meta.get(key, {})
        year = m.get("year") or r.get("year")

        f = films.setdefault(key, {
            "id": slug(m.get("title") or r["title"], year),
            "title": m.get("title") or r["title"],
            "year": year,
            "runtime": m.get("runtime") or 0,
            "director": m.get("director") or "",
            "cast": m.get("cast") or [],
            "genres": m.get("genres") or [],
            "critic": m.get("critic") or 0,
            "audience": m.get("audience") or 0,
            "popularity": m.get("popularity") or 0,
            "opened": m.get("opened") or "",
            "blurb": m.get("blurb") or "",
            "posterUrl": m.get("posterUrl"),
            "repertory": bool(year and year < dt.date.today().year - 2),
            # seed from any note carried over from the previous slate, so a
            # rerun doesn't lose a theater's own series framing
            "notes": [n for n in [m.get("note")] if n],
            "showings": [],
            "sources": [],
        })

        fmt = r.get("format") or "standard"
        if fmt == "standard":
            fmt = detect_format(f"{r.get('note','')} {r.get('title','')}")
        f["showings"].append(f"{r['theater']}|{day}|{hour:02d}:{t.minute:02d}|{fmt}")

        note = r.get("note") or extract_note(r.get("title", ""))
        if note and note not in f["notes"]:
            f["notes"].append(note)
        if r.get("source_url") and r["source_url"] not in f["sources"]:
            f["sources"].append(r["source_url"])
        # Fallback artwork from the theater's own page, when TMDB has nothing.
        if not f.get("posterUrl") and r.get("poster_url"):
            f["posterUrl"] = r["poster_url"]

    out = []
    for f in films.values():
        f["showings"] = sorted(set(f["showings"]))
        f["note"] = "; ".join(f.pop("notes")[:3])
        theaters = {s.split("|")[0] for s in f["showings"]}
        f["oneNight"] = len(f["showings"]) == 1
        f["soloTheater"] = len(theaters) == 1
        if not f["runtime"]:
            f["runtime"] = 110          # so runtime filters don't hide it
            f["runtimeUnknown"] = True
        out.append(f)
    return sorted(out, key=lambda f: (-f["popularity"], f["title"]))
