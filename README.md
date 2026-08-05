# Marquee

A weekend cinema dashboard for five Chicago theaters: AMC River East 21, AMC New City 14, Music Box, Gene Siskel Film Center, and the Logan.

Static site. No server, no database to host, no paid APIs. Free on GitHub Pages.

---

## Deploy it in ten minutes

You can get a live URL before writing a single scraper. Do that first — it's the fastest way to find out whether you'll actually use this.

### 1. Local check

```bash
npm install
npm run dev          # http://localhost:5173
```

You should see the dashboard with the demo slate and a red banner saying the data is fake.

### 2. Push to GitHub

```bash
git init
git add -A
git commit -m "marquee"
gh repo create marquee --public --source=. --push
```

No `gh`? Create an empty repo on github.com, then:

```bash
git remote add origin https://github.com/YOUR-USERNAME/marquee.git
git branch -M main && git push -u origin main
```

### 3. Set the base path

GitHub Pages serves project sites from `https://you.github.io/marquee/`, so Vite needs to know. In `vite.config.js`:

```js
base: "/marquee/",     // must match your repo name exactly, with both slashes
```

If you named the repo something else, change it here. Custom domain later? Set it to `"/"`.

**This is the step everyone gets wrong.** Wrong base path means a blank white page with 404s on the JS bundle in the console. If that happens, this line is why.

### 4. Turn on Pages

Repo → **Settings** → **Pages** → under Source pick **GitHub Actions** (not "Deploy from a branch").

### 5. Comment out the pipeline

The workflow tries to run scrapers that don't exist yet. Open `.github/workflows/deploy.yml` and delete or comment the block between the `--- listings ---` markers. Commit and push.

Actions tab → watch it run → your site is at `https://YOUR-USERNAME.github.io/marquee/`.

That's the deploy done. Everything below is filling in real data.

---

## Wiring up real listings

`src/slate.json` is the entire contract between the pipeline and the frontend:

```json
{
  "fetchedAt": "2026-08-07T17:04-05:00",
  "source": "live",
  "films": [ { "id": "...", "title": "...", "showings": ["logan|fri|19:15|standard"] } ]
}
```

Vite imports it at build time, so the pipeline just rewrites the file and the next build picks it up. No runtime fetch, no CORS, no API layer.

Three fields do real work:

- `source: "demo"` shows the red fake-data banner. Set it to `"live"` and the banner disappears.
- `fetchedAt` drives the header stamp and, past 30 hours, a "Stale" warning. **Don't remove this.** A broken scraper looks exactly like a quiet weekend unless the interface says when it last succeeded.
- `weekend` pins the three dates the listings were scraped for, as `["2026-08-07", "2026-08-08", "2026-08-09"]`. The day tabs label themselves from it, so the dates on screen can't disagree with the data behind them. If it's missing, the app falls back to computing the weekend from the clock.

### How the dates roll over

Monday through Thursday, the dashboard shows the coming Fri/Sat/Sun. On Friday, Saturday or Sunday it shows the weekend in progress and opens on today's tab rather than Friday. It rolls to the next weekend on Monday morning — so a Saturday refresh updates today's listings instead of jumping a week ahead.

`weekend_dates()` in the pipeline uses the identical rule, so the scrape and the labels always target the same three days. A tab left open from Sunday into Monday checks every 15 minutes and reloads itself when the weekend changes.

If a pinned `weekend` is in the past, the app says so in a banner rather than quietly showing dead listings.

Fill in `pipeline/run.py` one theater at a time. Each scraper is independent and guarded by `EXPECTED_MIN` — if one returns suspiciously few showings the run fails, GitHub emails you, and the previously committed `slate.json` stays live. That's your monitoring, free.

Start with AMC: it's an official free API and covers two of the five theaters in about an hour.

### Secrets

Repo → Settings → Secrets and variables → Actions:

| Secret | Where from | Cost |
|---|---|---|
| `AMC_KEY` | developers.amctheatres.com | Free |
| `TMDB_KEY` | themoviedb.org/settings/api | Free, personal use |

Then uncomment the listings block in the workflow.

---

## How it's put together

```
src/Marquee.jsx    the whole UI — filters, showtime ruler, plan tray, recommender
src/slate.json     listings; the pipeline rewrites this
pipeline/run.py    scrapers + normalization (skeleton)
.github/workflows/deploy.yml   cron Fri 5pm / Sat & Sun 8am, then build and deploy
```

Nothing in the app calls a paid API. "Picks for you" and the double-feature builder are rule-based JavaScript scoring against your taste profile. The plain-English ask box is optional, folded into a `<details>` section, and the only metered thing in the project — delete it if you want a permanently free build.

Watchlist, plan and taste profile persist in `localStorage`, so they're per-browser and never leave your machine.

---

## Other hosts

Pages is free and already wired up, but if you'd rather:

**Cloudflare Pages** — connect the repo, build `npm run build`, output `dist`, set `base: "/"`. Free tier, and a custom domain is free too.

**Netlify or Vercel** — same settings, same free tier. Both auto-detect Vite.

All three need `base: "/"` rather than `"/marquee/"`, since they serve from the domain root.

---

## Troubleshooting

**Blank page, 404s on `/assets/index-*.js`** — `base` doesn't match the repo name.

**Actions fails on `npm ci`** — commit `package-lock.json`.

**Actions fails on the Python step** — you haven't written the scrapers yet. Comment out the listings block.

**Site deploys but shows old listings** — the workflow commits `slate.json` back to the repo. Check that step succeeded; it needs `permissions: contents: write`, which is already set.

**Fonts don't load** — the component pulls Barlow Condensed, Karla and Space Mono from Google Fonts. Offline or blocked, it falls back to system fonts and looks worse but works. Self-host them if that bothers you.
