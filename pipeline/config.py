"""Everything you might want to change lives here."""

# Your five theaters. `dist` is miles from home — measure once, hardcode.
# They aren't moving, and this saves you a maps API.
THEATERS = {
    "musicbox":  {"name": "Music Box Theatre",       "short": "Music Box",  "dist": 3.1},
    "siskel":    {"name": "Gene Siskel Film Center", "short": "Siskel",     "dist": 4.9},
    "rivereast": {"name": "AMC River East 21",       "short": "River East", "dist": 5.6},
}

# AMC theatre IDs. Find yours by calling their Location or Theatre API
# and searching Chicago. Leave as None until you have them.
AMC_THEATRE_IDS = {
    "rivereast": None,   # AMC River East 21
}

# BigScreen theater ids — one plain-HTML source covering all five.
# See sources/bigscreen.py. This is the recommended default.
BIGSCREEN_IDS = {
    "musicbox": 940, "siskel": 937, "rivereast": 8267,
}

# Better sources where they exist, used in preference to BigScreen:
#   siskel -> its own Agile Ticketing calendar, which keeps series names
#             ("Technicolor Weekend", "25 for 25") that BigScreen drops.
SISKEL_CALENDAR = ("https://purchase.siskelfilmcenter.org/websales/pages/"
                   "list.aspx?epguid=a4b0e118-01a8-48f4-a68b-0dad266cea39")

# NOTE: musicboxtheatre.com/robots.txt disallows /calendar. Don't scrape
# it. BigScreen carries their listings and is fine to read.

# Calendar pages for the independents.
PAGES = {
    "musicbox": "https://musicboxtheatre.com/calendar",
    "siskel":   "https://www.siskelfilmcenter.org/",
}

# Sites that won't serve content without running JavaScript.
NEEDS_BROWSER = {"musicbox"}

# A quiet weekend day at each theater. Below this, assume the scraper
# broke rather than that nothing is playing.
EXPECTED_MIN = {
    "rivereast": 20, "siskel": 4, "musicbox": 3,
}

# Which formats we recognise. Anything else gets logged, not silently
# flattened to "standard" — premium formats are half the point.
FORMATS = {
    "imax": "imax", "imax with laser": "imax",
    "dolby cinema": "dolby", "dolby": "dolby",
    "70mm": "70mm", "35mm": "35mm", "16mm": "35mm",
    "3d": "3d", "realdinner": "3d",
    "4k restoration": "4k", "4k": "4k", "new restoration": "4k",
}

# Programming notes worth keeping. This is what aggregators throw away
# and the reason the independents are on your list at all.
NOTE_CUES = [
    "director in person", "q&a", "in person", "introduced by", "35mm print",
    "70mm print", "new restoration", "midnight", "matinee", "sing-along",
    "retrospective", "closing night", "opening night", "double feature",
    "presented by", "free admission", "members only", "sold out",
]
