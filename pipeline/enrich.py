"""Runtime, cast, genres, scores and posters.

Showtimes tell you when. They don't tell you anything your filters need.

Poster priority:
  1. TMDB          — consistent 2:3 artwork, licensed for exactly this use
  2. Theater page  — og:image, for things TMDB has never heard of
  3. Neither       — the app draws its own cover art
"""

import os, time, datetime as dt
import requests
from normalize import norm_title

TMDB = "https://api.themoviedb.org/3"
IMG = "https://image.tmdb.org/t/p/w342"      # w342 fits the card; w500 for retina

_cache: dict[str, dict] = {}

# Titles that will never match automatically. Repertory programming breaks
# every heuristic; twenty manual entries beat a cleverer matcher.
OVERRIDES = {
    # norm_title(...) : tmdb_id
    # "yiyi": 3115,
}


def _key():
    k = os.environ.get("TMDB_KEY")
    if not k:
        raise RuntimeError("TMDB_KEY not set")
    return k


def search(title: str, year=None) -> dict | None:
    params = {"api_key": _key(), "query": title, "include_adult": "false"}
    if year:
        params["year"] = year
    r = requests.get(f"{TMDB}/search/movie", params=params, timeout=20)
    r.raise_for_status()
    results = r.json().get("results", [])
    if not results:
        return None

    target = norm_title(title)
    best, best_score = None, -1
    for c in results[:8]:
        score = 0
        if norm_title(c.get("title", "")) == target:
            score += 60
        elif norm_title(c.get("original_title", "")) == target:
            score += 50
        rel = (c.get("release_date") or "")[:4]
        if year and rel:
            gap = abs(int(rel) - int(year))
            score += max(0, 25 - gap * 8)
        score += min(15, (c.get("popularity") or 0) / 8)
        if score > best_score:
            best, best_score = c, score

    # Below this, we'd be guessing. Guessing is how you end up showing
    # the wrong film's runtime next to a real showtime.
    return best if best_score >= 45 else None


def details(tmdb_id: int) -> dict:
    r = requests.get(f"{TMDB}/movie/{tmdb_id}",
                     params={"api_key": _key(), "append_to_response": "credits"},
                     timeout=20)
    r.raise_for_status()
    d = r.json()
    crew = d.get("credits", {}).get("crew", [])
    cast = d.get("credits", {}).get("cast", [])
    director = next((c["name"] for c in crew if c.get("job") == "Director"), "")
    return {
        "tmdb_id": tmdb_id,
        "title": d.get("title"),
        "year": int((d.get("release_date") or "0000")[:4]) or None,
        "runtime": d.get("runtime") or 0,
        "director": director,
        "cast": [c["name"] for c in cast[:4]],
        "genres": [g["name"] for g in d.get("genres", [])],
        "blurb": (d.get("overview") or "")[:220],
        "opened": d.get("release_date") or "",
        "popularity": round(d.get("popularity") or 0),
        "audience": round((d.get("vote_average") or 0) * 10),
        "posterUrl": IMG + d["poster_path"] if d.get("poster_path") else None,
        "imdb_id": d.get("imdb_id"),
    }


def omdb_scores(imdb_id: str) -> dict:
    """Rotten Tomatoes and Metacritic, via OMDb's free tier. Optional."""
    key = os.environ.get("OMDB_KEY")
    if not key or not imdb_id:
        return {}
    try:
        r = requests.get("https://www.omdbapi.com/",
                         params={"apikey": key, "i": imdb_id}, timeout=15)
        d = r.json()
        out = {}
        for rating in d.get("Ratings", []):
            if rating["Source"] == "Rotten Tomatoes":
                out["critic"] = int(rating["Value"].rstrip("%"))
        if d.get("Metascore", "N/A") != "N/A" and "critic" not in out:
            out["critic"] = int(d["Metascore"])
        return out
    except Exception:
        return {}


def enrich(titles: list[tuple[str, int | None]]) -> tuple[dict, list[str]]:
    """titles: [(display_title, year_or_None)] -> {norm_title: metadata}"""
    meta, unmatched = {}, []
    for title, year in titles:
        key = norm_title(title)
        if key in _cache:
            meta[key] = _cache[key]
            continue
        try:
            if key in OVERRIDES:
                d = details(OVERRIDES[key])
            else:
                hit = search(title, year)
                if not hit:
                    unmatched.append(f"{title} ({year or '?'})")
                    continue
                d = details(hit["id"])
            d.update(omdb_scores(d.get("imdb_id")))
            d.setdefault("critic", d.get("audience", 0))
            _cache[key] = d
            meta[key] = d
        except Exception as e:
            unmatched.append(f"{title}: {e}")
        time.sleep(0.25)      # be polite to a free API
    return meta, unmatched
