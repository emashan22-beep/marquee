"""Everything you might want to change lives here."""

# Your five theaters. `dist` is miles from home — measure once, hardcode.
# They aren't moving, and this saves you a maps API.
THEATERS = {
    "logan":     {"name": "Logan Theatre",           "short": "Logan",      "dist": 0.8},
    "newcity":   {"name": "AMC New City 14",         "short": "New City",   "dist": 2.7},
    "musicbox":  {"name": "Music Box Theatre",       "short": "Music Box",  "dist": 3.1},
    "siskel":    {"name": "Gene Siskel Film Center", "short": "Siskel",     "dist": 4.9},
    "rivereast": {"name": "AMC River East 21",       "short": "River East", "dist": 5.6},
}

# AMC theatre IDs. Find yours by calling their Location or Theatre API
# and searching Chicago. Leave as None until you have them.
AMC_THEATRE_IDS = {
    "rivereast": None,   # AMC River East 21
    "newcity":   None,   # AMC New City 14
}

# Calendar pages for the independents.
PAGES = {
    "musicbox": "https://musicboxtheatre.com/calendar",
    "siskel":   "https://www.siskelfilmcenter.org/",
    "logan":    "https://www.thelogantheatre.com/",
}

# Sites that won't serve content without running JavaScript.
NEEDS_BROWSER = {"musicbox"}

# A quiet weekend day at each theater. Below this, assume the scraper
# broke rather than that nothing is playing.
EXPECTED_MIN = {
    "rivereast": 20, "newcity": 15, "siskel": 4, "logan": 5, "musicbox": 3,
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
