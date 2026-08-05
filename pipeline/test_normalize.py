"""Run: python test_normalize.py — no network, no keys needed."""
import datetime as dt
from normalize import norm_title, build_slate, detect_format

WEEKEND = [dt.date(2026, 8, 7), dt.date(2026, 8, 8), dt.date(2026, 8, 9)]

def check(name, got, want):
    print(("  PASS  " if got == want else "  FAIL  ") + name)
    if got != want:
        print(f"        got  {got!r}\n        want {want!r}")
    return got == want

ok = True
print("title normalisation (the dedupe key)")
ok &= check("4K suffix stripped",  norm_title("Paris, Texas (4K Restoration)"), norm_title("Paris Texas"))
ok &= check("article ignored",     norm_title("The Shining"),                   norm_title("Shining"))
ok &= check("70mm tag ignored",    norm_title("The Shining — 70mm"),            norm_title("The Shining"))
ok &= check("accents folded",      norm_title("Cléo from 5 to 7"),              norm_title("Cleo from 5 to 7"))
ok &= check("different films differ", norm_title("Alien") != norm_title("Aliens"), True)

print("\nformat detection")
ok &= check("70mm from note", detect_format("presented in glorious 70mm"), "70mm")
ok &= check("plain text",     detect_format("regular screening"),          "standard")

print("\ndeduplication across theaters")
rows = [
    {"theater": "rivereast", "title": "Nightglass", "starts_at": "2026-08-07T19:40", "format": "imax",     "source_url": "a"},
    {"theater": "newcity",   "title": "Nightglass", "starts_at": "2026-08-07T20:15", "format": "standard", "source_url": "b"},
    {"theater": "logan",     "title": "NIGHTGLASS", "starts_at": "2026-08-08T21:00", "format": "standard", "source_url": "c"},
    {"theater": "musicbox",  "title": "The Shining (70mm)", "starts_at": "2026-08-09T00:00", "format": "70mm", "source_url": "d"},
    {"theater": "siskel",    "title": "Old News",   "starts_at": "2026-07-04T19:00", "format": "standard", "source_url": "e"},
]
slate = build_slate(rows, WEEKEND)
by = {f["title"].lower(): f for f in slate}
ok &= check("three listings became one film", len(slate), 2)
ok &= check("all three showings kept", len(by["nightglass"]["showings"]), 3)
ok &= check("premium format preserved", any("imax" in s for s in by["nightglass"]["showings"]), True)
ok &= check("plays at three theaters", by["nightglass"]["soloTheater"], False)
ok &= check("out-of-window screening dropped", "old news" in by, False)

print("\nafter-midnight handling")
sh = [f for f in slate if "shining" in f["title"].lower()][0]["showings"][0]
ok &= check("Sat midnight stays on Saturday", sh, "musicbox|sat|24:00|70mm")
ok &= check("flagged as a single screening", [f for f in slate if "shining" in f["title"].lower()][0]["oneNight"], True)

print("\n" + ("ALL PASS" if ok else "FAILURES ABOVE"))
raise SystemExit(0 if ok else 1)
