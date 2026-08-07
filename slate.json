#!/usr/bin/env python3
"""Marquee listings pipeline.

  python run.py --inspect musicbox      # look at a page before writing code
  python run.py --dry-run               # scrape and print, write nothing
  python run.py --only siskel           # one theater at a time
  python run.py --out ../src/slate.json # the real thing

Each theater is independent. One breaking never takes the others down,
and a broken scraper fails loudly rather than showing you an empty Friday.
"""

import argparse, json, sys, datetime as dt, traceback

from config import THEATERS, AMC_THEATRE_IDS, PAGES, NEEDS_BROWSER, EXPECTED_MIN
from sources import web, amc, extract, bigscreen
from normalize import build_slate, norm_title
import enrich as enrich_mod


def existing_meta(path: str) -> dict:
    """Metadata already present in the slate we're about to overwrite."""
    from normalize import norm_title
    try:
        with open(path) as fh:
            old = json.load(fh)
    except Exception:
        return {}
    keep = ("title", "year", "runtime", "director", "cast", "genres",
            "critic", "audience", "popularity", "opened", "blurb", "posterUrl",
            "note")
    out = {}
    for f in old.get("films", []):
        vals = {k: f[k] for k in keep if f.get(k) not in (None, "", [], 0)}
        if vals:
            out[norm_title(f["title"])] = vals
    return out


def weekend_dates(today=None):
    """Mon-Thu -> the coming weekend. Fri/Sat/Sun -> the one in progress.
    Rolls over Monday. Matches the rule the frontend uses."""
    today = today or dt.date.today()
    wd = today.weekday()                       # Mon=0 ... Sun=6
    friday = (today if wd == 4 else
              today - dt.timedelta(1) if wd == 5 else
              today - dt.timedelta(2) if wd == 6 else
              today + dt.timedelta(4 - wd))
    return [friday, friday + dt.timedelta(1), friday + dt.timedelta(2)]


# ---------------------------------------------------------------- sources

def scrape_amc(key, days):
    tid = AMC_THEATRE_IDS.get(key)
    if not tid:
        raise RuntimeError(f"no AMC theatre id for {key} — run --find-amc first")
    rows = []
    for d in days:
        rows += amc.to_rows(amc.showtimes(tid, d), key)
    return rows


def scrape_page(key, days, use_llm=True):
    url = PAGES[key]
    html = web.fetch(url, use_browser=key in NEEDS_BROWSER)
    text = web.page_text(html)
    poster = web.og_image(html, url)

    if use_llm:
        raw = extract.extract_llm(text, url)
    else:
        raw = hand_parse(key, html)            # write your own selectors

    kept, rejected = extract.validate(raw, text)
    for r in rejected:
        print(f"    dropped — {r}", file=sys.stderr)

    for r in kept:
        r["theater"] = key
        r.setdefault("source_url", url)
        r.setdefault("poster_url", poster)
    return kept


def hand_parse(key, html):
    """The free alternative to LLM extraction: your own selectors.

    Run `python run.py --inspect <theater>` first to see the page
    structure, then fill these in. Nothing here is guessed for you —
    guessing selectors is how you end up with confident wrong showtimes.
    """
    raise NotImplementedError(f"no hand-written parser for {key} yet; use --llm")


def scrape_bigscreen(key, days):
    """Default for every theater: one source, one parser, no keys."""
    return bigscreen.scrape_weekend(key, days)


SCRAPERS = {
    "rivereast": lambda d, llm: scrape_bigscreen("rivereast", d),
    "siskel":    lambda d, llm: scrape_bigscreen("siskel", d),
    "musicbox":  lambda d, llm: scrape_bigscreen("musicbox", d),
}

# Swap an entry for scrape_amc or scrape_page if you get a better source
# for that theater — e.g. the AMC vendor API, or Siskel's own calendar,
# which keeps series names that BigScreen drops.


# ------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="../src/slate.json")
    ap.add_argument("--only", action="append", help="just this theater (repeatable)")
    ap.add_argument("--dry-run", action="store_true", help="print, don't write")
    ap.add_argument("--inspect", metavar="THEATER", help="dump a page and exit")
    ap.add_argument("--find-amc", action="store_true", help="list AMC theatre ids near Chicago")
    ap.add_argument("--probe", metavar="THEATER",
                    help="diagnose one theater: what page came back, how many rows parsed")
    ap.add_argument("--llm", dest="llm", action="store_true", default=True)
    ap.add_argument("--no-llm", dest="llm", action="store_false",
                    help="use hand-written selectors instead of the API")
    ap.add_argument("--allow-partial", action="store_true",
                    help="write output even if some theaters failed")
    ap.add_argument("--no-enrich", action="store_true", help="skip TMDB")
    args = ap.parse_args()

    if args.find_amc:
        for t in amc.find_theatres("Chicago"):
            print(f"  {t['id']:>6}  {t['name']}  —  {t['address']}")
        return

    if args.probe:
        from sources import bigscreen as bs
        for d in weekend_dates():
            print(f"\n=== {args.probe}  {d:%a %b %d} ===")
            try:
                info = bs.probe(args.probe, d)
                for k in ("url", "bytes", "blocked", "is_directory", "page_says",
                          "date_ok", "rows_parsed"):
                    print(f"  {k:<13} {info[k]}")
                for line in info["sample"]:
                    print(f"    {line}")
                if not info["date_ok"]:
                    print(f"  text_head     {info['text_head'][:200]}")
            except Exception as e:
                print(f"  EXCEPTION     {type(e).__name__}: {e}")
        return

    if args.inspect:
        key = args.inspect
        html = web.fetch(PAGES[key], use_browser=key in NEEDS_BROWSER)
        text = web.page_text(html)
        print(f"--- {PAGES[key]}")
        print(f"--- {len(html):,} bytes of html, {len(text):,} of text")
        print(f"--- og:image: {web.og_image(html, PAGES[key])}")
        print(f"--- blocked: {web.looks_blocked(html)}")
        print("\n".join(text.splitlines()[:120]))
        return

    days = weekend_dates()
    print(f"weekend: {days[0]:%a %b %d} – {days[2]:%a %b %d}", file=sys.stderr)

    targets = args.only or list(SCRAPERS)
    rows, failures = [], []

    for key in targets:
        try:
            got = SCRAPERS[key](days, args.llm)
            if len(got) < EXPECTED_MIN[key] and not args.dry_run:
                raise RuntimeError(f"{len(got)} showings, expected {EXPECTED_MIN[key]}+ "
                                   f"— assume the scraper broke, not that nothing is playing")
            rows += got
            print(f"  {THEATERS[key]['short']:<12} {len(got):>4} showings", file=sys.stderr)
        except Exception as e:
            failures.append(f"{key}: {e}")
            print(f"  {THEATERS[key]['short']:<12} FAILED — {e}", file=sys.stderr)
            if args.dry_run:
                traceback.print_exc()

    if not rows:
        raise SystemExit("nothing scraped; leaving the existing slate alone")

    # Start from whatever the existing slate already knows. Otherwise a
    # keyless rerun would throw away directors, cast and years that are
    # already correct.
    meta, unmatched = {}, []
    meta.update(existing_meta(args.out))

    if not args.no_enrich:
        titles = sorted({(r["title"], r.get("year")) for r in rows},
                        key=lambda t: (t[0].lower(), t[1] or 0))
        fresh, unmatched = enrich_mod.enrich(titles)
        for k, v in fresh.items():
            meta.setdefault(k, {}).update({a: b for a, b in v.items() if b not in (None, "", [], 0)})
        for u in unmatched:
            print(f"    unmatched — {u}", file=sys.stderr)

    # BigScreen prints runtimes on the listing page; use them where TMDB
    # gave us nothing, so the runtime filter still works without a key.
    from normalize import norm_title
    for r in rows:
        k = norm_title(r["title"])
        if r.get("runtime_hint") and not meta.get(k, {}).get("runtime"):
            meta.setdefault(k, {}).update({"runtime": r["runtime_hint"], "title": r["title"]})

    films = build_slate(rows, days, meta)
    missing_art = [f["title"] for f in films if not f.get("posterUrl")]

    print(f"\n{len(films)} films, {len(rows)} showings", file=sys.stderr)
    if amc.unmapped_attributes():
        print(f"unmapped AMC attributes: {sorted(amc.unmapped_attributes())}", file=sys.stderr)
    if missing_art:
        print(f"no poster for: {', '.join(missing_art)}", file=sys.stderr)

    payload = {
        "fetchedAt": dt.datetime.now().astimezone().isoformat(timespec="minutes"),
        "source": "live",
        "weekend": [d.isoformat() for d in days],
        "partial": failures,
        "unmatched": unmatched,
        "films": films,
    }

    if args.dry_run:
        for f in films:
            print(f"\n{f['title']} ({f['year']}) {f['runtime']}min — {f['director']}")
            print(f"  poster: {'yes' if f.get('posterUrl') else 'NO'}   note: {f.get('note') or '-'}")
            for s in f["showings"]:
                print(f"  {s}")
        return

    if failures:
        print("\n" + "=" * 60, file=sys.stderr)
        print("THEATERS THAT FAILED:", file=sys.stderr)
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        if not args.allow_partial:
            raise SystemExit(
                "Stopping because --allow-partial was not set. "
                "Re-run with --allow-partial to publish the theaters that did work."
            )
        print("Continuing with --allow-partial; the site will show a "
              "'Partial' banner naming the misses.", file=sys.stderr)

    with open(args.out, "w") as fh:
        json.dump(payload, fh, indent=2)
    print(f"wrote {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
