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
from sources import web, amc, extract
from normalize import build_slate, norm_title
import enrich as enrich_mod


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


SCRAPERS = {
    "rivereast": lambda d, llm: scrape_amc("rivereast", d),
    "newcity":   lambda d, llm: scrape_amc("newcity", d),
    "siskel":    lambda d, llm: scrape_page("siskel", d, llm),
    "logan":     lambda d, llm: scrape_page("logan", d, llm),
    "musicbox":  lambda d, llm: scrape_page("musicbox", d, llm),
}


# ------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="../src/slate.json")
    ap.add_argument("--only", action="append", help="just this theater (repeatable)")
    ap.add_argument("--dry-run", action="store_true", help="print, don't write")
    ap.add_argument("--inspect", metavar="THEATER", help="dump a page and exit")
    ap.add_argument("--find-amc", action="store_true", help="list AMC theatre ids near Chicago")
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

    meta, unmatched = {}, []
    if not args.no_enrich:
        titles = sorted({(r["title"], r.get("year")) for r in rows})
        meta, unmatched = enrich_mod.enrich(titles)
        for u in unmatched:
            print(f"    unmatched — {u}", file=sys.stderr)

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

    if failures and not args.allow_partial:
        raise SystemExit("failed:\n  " + "\n  ".join(failures))

    with open(args.out, "w") as fh:
        json.dump(payload, fh, indent=2)
    print(f"wrote {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
