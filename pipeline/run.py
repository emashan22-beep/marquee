"""Marquee listings pipeline.

Writes src/slate.json in the shape the frontend expects. Every scraper
lives in its own function so one theater breaking doesn't take the rest
down with it.

Right now this is a skeleton: it passes the existing slate through and
marks it as demo. Fill in the scrapers one at a time — start with AMC.
"""

import argparse, json, os, sys, datetime as dt

# A normal weekend day at each theater. If a scraper returns fewer than
# this, something broke — fail loudly rather than showing an empty grid.
EXPECTED_MIN = {"rivereast": 20, "newcity": 15, "siskel": 5, "logan": 6, "musicbox": 3}


class ScraperBroke(Exception):
    pass


def fetch_amc(theatre_id, days):
    """AMC River East 21 and New City 14. Free vendor key from
    developers.amctheatres.com/GettingStarted/NewVendorRequest"""
    raise NotImplementedError("start here — see marquee-free-build.md")


def fetch_siskel(days):
    """Plain server-rendered HTML. requests + BeautifulSoup, no browser."""
    raise NotImplementedError


def fetch_logan(days):
    """Also plain HTML."""
    raise NotImplementedError


def fetch_musicbox(days):
    """Behind a JS check — needs Playwright to render before parsing."""
    raise NotImplementedError


SCRAPERS = {
    # "rivereast": lambda d: fetch_amc(RIVER_EAST_ID, d),
    # "newcity":   lambda d: fetch_amc(NEW_CITY_ID, d),
    # "siskel":    fetch_siskel,
    # "logan":     fetch_logan,
    # "musicbox":  fetch_musicbox,
}


def weekend_dates(today=None):
    """The weekend to scrape.

    Mon-Thu  -> the coming Fri/Sat/Sun.
    Fri/Sat/Sun -> the one in progress, so a Saturday refresh updates
                   today's listings instead of jumping a week ahead.
    Rolls over on Monday.

    (Python weekday(): Mon=0 ... Fri=4, Sat=5, Sun=6)
    """
    today = today or dt.date.today()
    wd = today.weekday()
    if wd == 4:                      # Friday
        friday = today
    elif wd == 5:                    # Saturday
        friday = today - dt.timedelta(1)
    elif wd == 6:                    # Sunday
        friday = today - dt.timedelta(2)
    else:                            # Mon-Thu
        friday = today + dt.timedelta(4 - wd)
    return [friday, friday + dt.timedelta(1), friday + dt.timedelta(2)]


DAY_ID = {4: "fri", 5: "sat", 6: "sun"}   # weekday() -> the id the frontend uses


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="src/slate.json")
    ap.add_argument("--allow-partial", action="store_true",
                    help="write output even if a scraper fails")
    args = ap.parse_args()

    days = weekend_dates()
    rows, failures = [], []

    for theater, scrape in SCRAPERS.items():
        try:
            got = scrape(days)
            if len(got) < EXPECTED_MIN[theater]:
                raise ScraperBroke(f"{theater}: {len(got)} showings, expected {EXPECTED_MIN[theater]}+")
            rows += got
            print(f"  {theater:12} {len(got):4} showings", file=sys.stderr)
        except Exception as e:
            failures.append(f"{theater}: {e}")
            print(f"  {theater:12} FAILED — {e}", file=sys.stderr)

    if not SCRAPERS:
        print("No scrapers wired up yet; leaving the demo slate in place.", file=sys.stderr)
        return 0

    if failures and not args.allow_partial:
        # A failed run emails you automatically. That's the monitoring.
        raise SystemExit("scrapers failed:\n  " + "\n  ".join(failures))

    films = normalize(rows)   # dedupe on title+year, merge showings, join TMDB
    with open(args.out, "w") as f:
        json.dump({
            "fetchedAt": dt.datetime.now().astimezone().isoformat(timespec="minutes"),
            "source": "live",
            # Pin the dates these listings are for. The frontend labels its
            # tabs from this, so the dates on screen can never disagree with
            # the data behind them.
            "weekend": [d.isoformat() for d in days],
            "partial": failures,
            "films": films,
        }, f, indent=2)
    print(f"wrote {len(films)} films to {args.out}", file=sys.stderr)


def normalize(rows):
    raise NotImplementedError("dedupe on title+year, merge showings, join TMDB")


if __name__ == "__main__":
    main()
