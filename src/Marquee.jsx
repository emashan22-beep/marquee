import React, { useState, useEffect, useMemo, useRef } from "react";
import slateData from "./slate.json";

/* ------------------------------------------------------------------
   MARQUEE — a weekend cinema dashboard for five Chicago theaters.
   Listings come from src/slate.json, which the pipeline rewrites
   before each build. Schema documented at the bottom of this file.
------------------------------------------------------------------- */

const THEATERS = [
  { id: "musicbox", name: "Music Box Theatre", short: "Music Box", hood: "Lakeview", addr: "3733 N Southport Ave", dist: 3.1 },
  { id: "siskel", name: "Gene Siskel Film Center", short: "Siskel", hood: "The Loop", addr: "164 N State St", dist: 4.9 },
  { id: "rivereast", name: "AMC River East 21", short: "River East", hood: "Streeterville", addr: "322 E Illinois St", dist: 5.6 },
];
const T = Object.fromEntries(THEATERS.map((t) => [t.id, t]));
// Slider bounds follow the theater list — no dead space below the
// nearest theater now that the list is shorter.
const DIST_MIN = Math.floor(Math.min(...THEATERS.map((t) => t.dist)) * 2) / 2;
const DIST_MAX = Math.ceil(Math.max(...THEATERS.map((t) => t.dist)) * 2) / 2;

/* ---- which weekend are we showing? --------------------------------
   Mon–Thu  → the coming Fri/Sat/Sun.
   Fri/Sat/Sun → the one currently in progress.
   So it rolls over on Monday morning and never shows a weekend that
   has already finished. If slate.json pins the dates it was scraped
   for, those win — the labels must match the data, not the clock. */

const midnight = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate());
const addDays = (d, n) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);

function weekendOf(now = new Date()) {
  const today = midnight(now);
  const wd = today.getDay(); // 0 Sun … 5 Fri, 6 Sat
  const friday =
    wd === 5 ? today :
    wd === 6 ? addDays(today, -1) :
    wd === 0 ? addDays(today, -2) :
               addDays(today, 5 - wd);
  return [friday, addDays(friday, 1), addDays(friday, 2)];
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const fmtDate = (d) => `${MONTHS[d.getMonth()]} ${d.getDate()}`;
const toISO = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

const WEEKEND =
  Array.isArray(slateData.weekend) && slateData.weekend.length === 3
    ? slateData.weekend.map((iso) => new Date(`${iso}T00:00`))
    : weekendOf();

const DAYS = [
  { id: "fri", label: "Fri", date: fmtDate(WEEKEND[0]), iso: toISO(WEEKEND[0]) },
  { id: "sat", label: "Sat", date: fmtDate(WEEKEND[1]), iso: toISO(WEEKEND[1]) },
  { id: "sun", label: "Sun", date: fmtDate(WEEKEND[2]), iso: toISO(WEEKEND[2]) },
];

// If today is part of this weekend, open on today rather than Friday.
const TODAY_ID = DAYS.find((d) => d.iso === toISO(new Date()))?.id || "fri";
// True when the pinned slate is for a weekend that has already ended.
const WEEKEND_OVER = midnight(new Date()) > WEEKEND[2];

const FORMAT_LABEL = {
  imax: "IMAX",
  dolby: "Dolby",
  "70mm": "70mm",
  "35mm": "35mm",
  "3d": "3D",
  "4k": "4K restoration",
  standard: "Standard",
};
const PREMIUM = ["imax", "dolby", "70mm", "35mm", "3d", "4k"];

// showing string format: "theater|day|HH:MM|format"
const SLATE = slateData.films;
const FETCHED_AT = slateData.fetchedAt;

/* ---------------------------- helpers ---------------------------- */

const parseShowing = (s, filmId) => {
  const [theater, day, time, format] = s.split("|");
  const [h, m] = time.split(":").map(Number);
  return { filmId, theater, day, format, mins: h * 60 + m, key: `${filmId}|${s}` };
};

const ALL_SHOWINGS = SLATE.flatMap((f) => f.showings.map((s) => parseShowing(s, f.id)));
const FILM_BY_ID = Object.fromEntries(SLATE.map((f) => [f.id, f]));

const fmtTime = (mins) => {
  let m = mins % 1440;
  const h24 = Math.floor(m / 60);
  const mm = String(m % 60).padStart(2, "0");
  const ap = h24 >= 12 && h24 < 24 ? "PM" : "AM";
  let h = h24 % 12;
  if (h === 0) h = 12;
  return `${h}:${mm} ${ap}`;
};
const fmtRuntime = (m) => `${Math.floor(m / 60)}h ${String(m % 60).padStart(2, "0")}m`;
const travelMins = (a, b) => (a === b ? 0 : Math.max(12, Math.round(9 + Math.abs(T[a].dist - T[b].dist) * 5)));

const GENRES = [...new Set(SLATE.flatMap((f) => f.genres))].sort();

const filmTheaters = (film, day) => {
  const set = new Set(film.showings.map(parseShowing).filter((s) => !day || s.day === day).map((s) => s.theater));
  return THEATERS.filter((t) => set.has(t.id));
};
const filmFormats = (film, day) => [
  ...new Set(film.showings.map(parseShowing).filter((s) => !day || s.day === day).map((s) => s.format)),
];
const earliestMins = (showings) => (showings.length ? Math.min(...showings.map((s) => s.mins)) : 9999);
/* Rule-based recommender. No API, no key, no cost — runs on the
   taste profile you set in the app. */
const splitList = (s) => (s || "").split(",").map((x) => x.trim().toLowerCase()).filter(Boolean);

const scoreFilm = (f, day, profile, watchlist) => {
  let score = 0;
  const why = [];
  const hits = profile.genres.filter((g) => f.genres.includes(g));
  if (hits.length) {
    score += 14 * hits.length;
    why.push(`${hits.map((h) => h.toLowerCase()).join(" and ")} is your lane`);
  }
  const dirs = splitList(profile.directors);
  if (dirs.some((d) => f.director.toLowerCase().includes(d))) {
    score += 32;
    why.push(`${f.director} is a director you follow`);
  }
  splitList(profile.loved).forEach((l) => {
    const m = SLATE.find((x) => x.title.toLowerCase() === l);
    if (!m || m.id === f.id) return;
    if (m.director === f.director) {
      score += 24;
      why.push(`same director as ${m.title}`);
    }
    const shared = m.cast.filter((c) => f.cast.includes(c));
    if (shared.length) {
      score += 12;
      why.push(`${shared[0]} again`);
    }
  });
  if (watchlist.includes(f.id)) {
    score += 40;
    why.push("already on your watchlist");
  }
  score += (f.critic - 62) * 0.4;
  if (f.lastWeekend) { score += 14; why.push("leaves after Sunday"); }
  if (f.oneNight) { score += 11; why.push("one screening only"); }
  if (f.isNew) { score += 6; }
  const ts = filmTheaters(f, day);
  if (ts.length === 1) { score += 5; why.push(`only at ${ts[0].short}`); }
  const d = nearestDist(f, day);
  score -= d * 1.6;
  return { score, why, dist: d };
};

const nearestDist = (film, day) => {
  const ts = filmTheaters(film, day);
  return ts.length ? Math.min(...ts.map((t) => t.dist)) : 99;
};

const GEL = ["#3B4B8C", "#7A3B5E", "#2F6B5F", "#8A5A2B", "#553B7A", "#1F4E6B", "#6B4A2F", "#2E5E7A"];
const gelFor = (id) => GEL[[...id].reduce((a, c) => a + c.charCodeAt(0), 0) % GEL.length];

/* ------------------------- storage wrapper ------------------------ */

const load = async (key, fallback) => {
  try {
    const v = localStorage.getItem(key);
    return v ? JSON.parse(v) : fallback;
  } catch {
    return fallback;
  }
};
const save = async (key, value) => {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* private browsing; state still works this session */
  }
};

/* ----------------------------- styles ----------------------------- */

const CSS = `
@import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600;700&family=Karla:wght@400;500;700&family=Space+Mono:wght@400;700&display=swap');

html { scrollbar-gutter: stable; }
.mq { --house:#13152A; --balcony:#1C2040; --rail:#2A2F58; --bulb:#FFB84D; --screen:#F0EDE3;
      --dim:#9BA0C4; --exit:#FF6B5A; --reel:#6FD8C6;
      background:var(--house); color:var(--screen); min-height:100vh;
      font-family:'Karla',system-ui,sans-serif; -webkit-font-smoothing:antialiased; }
.mq *,.mq *::before,.mq *::after { box-sizing:border-box; }
.mq button { font:inherit; color:inherit; background:none; border:none; cursor:pointer; }
.mq :focus-visible { outline:2px solid var(--bulb); outline-offset:2px; border-radius:2px; }
.mq-cond { font-family:'Barlow Condensed',Impact,sans-serif; text-transform:uppercase; letter-spacing:.02em; }
.mq-mono { font-family:'Space Mono',ui-monospace,monospace; }
.mq-wrap { max-width:1180px; margin:0 auto; padding:0 20px 200px; }

/* marquee header */
.mq-bulbs { height:14px; background:
   radial-gradient(circle at 9px 7px, var(--bulb) 0 3px, transparent 3.5px) repeat-x;
   background-size:24px 14px; opacity:.85; }
.mq-head { padding:26px 0 18px; border-bottom:1px solid var(--rail); }
.mq-mark { font-family:'Barlow Condensed',Impact,sans-serif; font-weight:700; font-size:44px;
   line-height:.9; letter-spacing:.06em; text-transform:uppercase; color:var(--bulb); }
.mq-sub { font-size:13px; color:var(--dim); margin-top:6px; letter-spacing:.04em; }
.mq-stat { display:flex; flex-wrap:wrap; gap:18px; margin-top:14px; }
.mq-stat span { font-size:12px; color:var(--dim); }
.mq-stat b { color:var(--screen); font-weight:700; }

/* day tabs */
.mq-days { display:flex; gap:8px; }
.mq-day { padding:8px 16px; border:1px solid var(--rail); border-radius:999px; background:var(--balcony); }
.mq-day.on { background:var(--bulb); color:#13152A; border-color:var(--bulb); font-weight:700; }
.mq-day .d { font-family:'Barlow Condensed',sans-serif; text-transform:uppercase; font-size:17px; letter-spacing:.05em; }
.mq-day .n { font-family:'Space Mono',monospace; font-size:11px; opacity:.7; margin-left:6px; }

/* ask bar */
.mq-ask { margin:22px 0 4px; background:var(--balcony); border:1px solid var(--rail); border-radius:10px; padding:14px; }
.mq-ask-row { display:flex; gap:10px; flex-wrap:wrap; }
.mq-input { flex:1 1 260px; background:#10122270; border:1px solid var(--rail); border-radius:8px;
   padding:11px 13px; color:var(--screen); font-size:14px; }
.mq-input::placeholder { color:#6E739B; }
.mq-btn { background:var(--bulb); color:#13152A; font-weight:700; padding:11px 18px; border-radius:8px; font-size:14px; }
.mq-btn:disabled { opacity:.5; cursor:default; }
.mq-btn-ghost { border:1px solid var(--rail); padding:9px 14px; border-radius:8px; font-size:13px; color:var(--dim); }
.mq-btn-ghost:hover { color:var(--screen); border-color:var(--bulb); }
.mq-chiprow { display:flex; gap:8px; flex-wrap:wrap; margin-top:10px; }
.mq-seed { font-size:12px; color:var(--dim); border:1px dashed var(--rail); border-radius:999px; padding:5px 11px; }
.mq-seed:hover { color:var(--bulb); border-color:var(--bulb); }
.mq-freetag { font-size:11px; color:var(--reel); align-self:center; letter-spacing:.06em; }
.mq-optional { margin-top:14px; border-top:1px dashed var(--rail); padding-top:12px; }
.mq-optional summary { font-size:12.5px; color:var(--dim); cursor:pointer; list-style:none; }
.mq-optional summary::before { content:'+ '; color:var(--bulb); }
.mq-optional[open] summary::before { content:'– '; }
.mq-optional summary:hover { color:var(--screen); }
.mq-answer { margin-top:12px; padding:12px 14px; background:#FFB84D14; border-left:2px solid var(--bulb);
   border-radius:0 6px 6px 0; font-size:14px; line-height:1.55; }

/* filters */
.mq-filters { display:grid; grid-template-columns:repeat(auto-fit,minmax(210px,1fr)); gap:18px;
   padding:18px 0; border-bottom:1px solid var(--rail); }
.mq-flabel { font-family:'Barlow Condensed',sans-serif; text-transform:uppercase; font-size:12px;
   letter-spacing:.14em; color:var(--dim); margin-bottom:9px; }
.mq-chip { font-size:12px; padding:5px 10px; border:1px solid var(--rail); border-radius:6px; background:var(--balcony); color:var(--dim); }
.mq-chip.on { background:var(--bulb); color:#13152A; border-color:var(--bulb); font-weight:700; }
.mq-chip .mi { font-family:'Space Mono',monospace; font-size:10px; opacity:.65; margin-left:5px; }
.mq-range { width:100%; accent-color:var(--bulb); }
.mq-rangeval { font-family:'Space Mono',monospace; font-size:12px; color:var(--bulb); }

/* toolbar */
.mq-tools { display:flex; justify-content:space-between; align-items:center; gap:14px; flex-wrap:wrap; padding:16px 0; }
.mq-count { font-family:'Barlow Condensed',sans-serif; text-transform:uppercase; letter-spacing:.1em; font-size:14px; color:var(--dim); }
.mq-select { background:var(--balcony); border:1px solid var(--rail); color:var(--screen); border-radius:7px; padding:8px 11px; font-size:13px; }

/* film card */
.mq-card { display:grid; grid-template-columns:132px 1fr; gap:20px; padding:22px 0; border-bottom:1px solid var(--rail); }
.mq-poster { aspect-ratio:2/3; border-radius:4px; padding:11px; display:flex; flex-direction:column; justify-content:flex-end;
   position:relative; overflow:hidden; }
.mq-art { position:absolute; inset:0; width:100%; height:100%; object-fit:cover; }
.mq-poster.has-art { padding:0; background:#0E1024; }
.mq-plate { position:relative; z-index:2; width:100%; height:100%; display:flex; flex-direction:column;
   border:1px solid #ffffff33; border-radius:2px; padding:10px 9px; }
.mq-plate .ptop { font-family:'Space Mono',monospace; font-size:8.5px; letter-spacing:.16em;
   text-transform:uppercase; color:#ffffffc0; }
.mq-plate .pt { margin-top:auto; font-family:'Barlow Condensed',sans-serif; font-weight:700;
   text-transform:uppercase; font-size:20px; line-height:.94; color:#fff; }
.mq-plate .prule { height:1px; background:#ffffff4D; margin:8px 0 7px; }
.mq-plate .pmeta { font-family:'Space Mono',monospace; font-size:8.5px; line-height:1.4;
   color:#ffffffb3; letter-spacing:.02em; }
.mq-firstAt { font-size:11px; letter-spacing:.1em; text-transform:uppercase; color:var(--bulb); margin-bottom:5px; }
.mq-title { font-family:'Barlow Condensed',sans-serif; font-weight:700; text-transform:uppercase;
   font-size:29px; line-height:1; letter-spacing:.01em; }
.mq-meta { font-size:13px; color:var(--dim); margin-top:6px; }
.mq-meta em { font-style:normal; color:var(--screen); }
.mq-progNote { font-size:12.5px; color:var(--reel); margin-top:9px; letter-spacing:.02em; }
.mq-blurb { font-size:13.5px; line-height:1.5; color:#C7CBE6; margin-top:9px; max-width:62ch; }
.mq-badges { display:flex; gap:7px; flex-wrap:wrap; margin-top:10px; }
.mq-badge { font-family:'Barlow Condensed',sans-serif; text-transform:uppercase; font-size:11px;
   letter-spacing:.1em; padding:3px 8px; border-radius:3px; border:1px solid currentColor; }
.b-only { color:var(--reel); } .b-last { color:var(--exit); } .b-new { color:var(--bulb); }
.b-fmt { color:#B9BEE4; } .b-one { color:var(--reel); }
.mq-scores { display:flex; gap:14px; margin-top:11px; align-items:baseline; }
.mq-score b { font-family:'Space Mono',monospace; font-size:16px; }
.mq-score span { font-size:11px; color:var(--dim); margin-left:5px; }
.sc-none { color:#5A5F85; }
.sc-hi { color:var(--reel); } .sc-mid { color:var(--bulb); } .sc-lo { color:var(--exit); }
.mq-cardtools { display:flex; gap:10px; margin-top:14px; align-items:center; flex-wrap:wrap; }
.mq-star { font-size:12px; color:var(--dim); border:1px solid var(--rail); border-radius:6px; padding:6px 11px; }
.mq-star.on { color:var(--bulb); border-color:var(--bulb); }


/* showtimes — one shape everywhere */
.mq-times { margin-top:14px; background:var(--balcony); border:1px solid var(--rail); border-radius:9px; padding:6px 14px; }
.mq-trow { display:flex; align-items:baseline; gap:14px; padding:11px 0; }
.mq-trow + .mq-trow { border-top:1px dashed #ffffff12; }
.mq-tname { width:100px; flex:none; font-family:'Barlow Condensed',sans-serif; text-transform:uppercase;
   font-size:14px; letter-spacing:.06em; color:var(--dim); }
.mq-tname i { display:block; font-style:normal; font-family:'Space Mono',monospace;
   font-size:9.5px; color:#6E739B; letter-spacing:0; }
.mq-chips { display:flex; flex-wrap:wrap; gap:7px; }
.mq-show { font-family:'Space Mono',monospace; font-size:12px; padding:5px 9px; border-radius:5px;
   background:#3A4076; border:1px solid #4A5192; color:var(--screen); white-space:nowrap; }
.mq-show:hover { background:var(--bulb); color:#13152A; border-color:var(--bulb); }
.mq-show.picked { background:var(--bulb); color:#13152A; border-color:var(--bulb); font-weight:700; }
.mq-show.prem { border-color:var(--reel); }
.mq-show sup { font-size:8.5px; letter-spacing:.06em; margin-left:4px; opacity:.85; text-transform:uppercase; }

/* plan tray */
.mq-tray { position:fixed; left:0; right:0; bottom:0; background:#0E1024F2; border-top:1px solid var(--bulb);
   backdrop-filter:blur(8px); z-index:40; }
.mq-trayIn { max-width:1180px; margin:0 auto; padding:12px 20px 16px; }
.mq-trayHead { display:flex; justify-content:space-between; align-items:center; gap:12px; }
.mq-trayTitle { font-family:'Barlow Condensed',sans-serif; text-transform:uppercase; letter-spacing:.12em; font-size:14px; color:var(--bulb); }
.mq-plan { display:flex; gap:10px; overflow-x:auto; padding-top:11px; }
.mq-planItem { flex:none; min-width:200px; background:var(--balcony); border:1px solid var(--rail);
   border-radius:8px; padding:10px 12px; }
.mq-planItem .t { font-family:'Barlow Condensed',sans-serif; text-transform:uppercase; font-size:16px; line-height:1.05; }
.mq-planItem .d { font-family:'Space Mono',monospace; font-size:11px; color:var(--dim); margin-top:4px; }
.mq-warn { color:var(--exit); font-size:12px; margin-top:9px; }
.mq-ok { color:var(--reel); font-size:12px; margin-top:9px; }

/* modal */
.mq-modalbg { position:fixed; inset:0; background:#080915D9; display:flex; align-items:center;
   justify-content:center; padding:20px; z-index:60; }
.mq-modal { background:var(--house); border:1px solid var(--rail); border-radius:12px; max-width:540px;
   width:100%; max-height:86vh; overflow:auto; padding:24px; }
.mq-h2 { font-family:'Barlow Condensed',sans-serif; text-transform:uppercase; letter-spacing:.06em; font-size:24px; }
.mq-foot { margin-top:34px; padding-top:18px; border-top:1px solid var(--rail); }
.mq-link { color:var(--dim); text-decoration:underline; text-underline-offset:2px; }
.mq-link:hover { color:var(--bulb); }
.mq-note { font-size:12.5px; color:var(--dim); line-height:1.55; }
.mq-empty { padding:56px 0; text-align:center; color:var(--dim); }
.mq-empty p { font-size:14px; margin-top:8px; }

.mq-fake { background:#FF6B5A18; border-bottom:1px solid var(--exit); }
.mq-fakeIn { max-width:1180px; margin:0 auto; padding:11px 20px; font-size:13px; line-height:1.5; color:#FFD9D3; }
.mq-fakeIn b { color:var(--exit); font-family:'Barlow Condensed',sans-serif; text-transform:uppercase;
   letter-spacing:.12em; font-size:14px; }
.mq-alert { margin-top:16px; border:1px solid var(--bulb); border-radius:9px; padding:12px 14px;
   background:#FFB84D12; font-size:13.5px; }
.mq-spin { display:inline-block; width:13px; height:13px; border:2px solid #13152A55;
   border-top-color:#13152A; border-radius:50%; animation:mqspin .7s linear infinite; vertical-align:-2px; margin-right:7px; }
@keyframes mqspin { to { transform:rotate(360deg); } }
@media (prefers-reduced-motion:reduce) { .mq-spin { animation-duration:2.4s; } }
@media (max-width:640px) {
  .mq-card { grid-template-columns:96px 1fr; gap:14px; }
  .mq-poster .pt { font-size:15px; }
  .mq-title { font-size:23px; }
  .mq-mark { font-size:33px; }
  .mq-trow { flex-direction:column; gap:6px; }
  .mq-tname { width:auto; }
}
`;

/* ------------------------- small components ----------------------- */

const scoreClass = (n) => (n >= 80 ? "sc-hi" : n >= 60 ? "sc-mid" : "sc-lo");

/* Placeholder cover.

   This is NOT meant to look like a poster — a fake poster for a real film
   misrepresents it. It's a repertory programme card: the title set large,
   the facts underneath, a format stamp. It reads as "we don't have the
   artwork yet" rather than as bad art.

   Real posters arrive the moment TMDB_KEY is set; see enrich.py. */
function Poster({ film }) {
  if (film.posterUrl) {
    return (
      <div className="mq-poster has-art">
        <img className="mq-art" src={film.posterUrl} alt={`${film.title} poster`} loading="lazy" />
      </div>
    );
  }
  const prem = (film.showings || [])
    .map((x) => x.split("|")[3])
    .find((x) => PREMIUM.includes(x));
  const line = [film.director, film.genres?.[0]].filter(Boolean)[0] || "";
  return (
    <div className="mq-poster" style={{ background: gelFor(film.id) }}>
      <div className="mq-plate">
        <div className="ptop">{prem ? FORMAT_LABEL[prem] : film.year || ""}</div>
        <div className="pt">{film.title}</div>
        <div className="prule" />
        <div className="pmeta">
          {line}
          {film.year && line ? ` · ${film.year}` : ""}
        </div>
      </div>
    </div>
  );
}

/* Compact label. Cinemas print evening times bare and mark mornings, so
   9:45a and 9:45 are unambiguous without the extra characters. */
const fmtShort = (mins) => {
  const m = mins % 1440;
  const h24 = Math.floor(m / 60);
  const isAM = h24 < 12;
  const h = h24 % 12 || 12;
  return `${h}:${String(m % 60).padStart(2, "0")}${isAM ? "a" : ""}`;
};

/* One row per theater, times in order. Identical for a single screening
   and for twenty-two — the axis version rendered two different shapes
   depending on how busy a theater was, which made the page read as if
   it were built by two different people. */
function Showtimes({ film, day, picked, onPick, keep }) {
  const shows = film.showings
    .map((s) => parseShowing(s, film.id))
    .filter((s) => s.day === day && (!keep || keep(s)));
  const byTheater = THEATERS.filter((t) => shows.some((s) => s.theater === t.id));
  if (!byTheater.length) return null;

  return (
    <div className="mq-times">
      {byTheater.map((t) => {
        const lane = shows.filter((s) => s.theater === t.id).sort((a, b) => a.mins - b.mins);
        return (
          <div className="mq-trow" key={t.id}>
            <div className="mq-tname">
              {t.short}
              <i>{t.dist} mi</i>
            </div>
            <div className="mq-chips">
              {lane.map((s) => {
                const prem = PREMIUM.includes(s.format);
                const on = picked.includes(s.key);
                return (
                  <button
                    key={s.key}
                    className={`mq-show${prem ? " prem" : ""}${on ? " picked" : ""}`}
                    onClick={() => onPick(s)}
                    title={`${fmtTime(s.mins)} · ${t.name} · ${FORMAT_LABEL[s.format]} — ${on ? "remove from plan" : "add to plan"}`}
                  >
                    {fmtShort(s.mins)}
                    {prem && <sup>{FORMAT_LABEL[s.format]}</sup>}
                  </button>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* --------------------------- main app ----------------------------- */

export default function Marquee() {
  const [day, setDay] = useState(TODAY_ID);
  const [theaterSel, setTheaterSel] = useState([]);
  const [genreSel, setGenreSel] = useState([]);
  const [formatSel, setFormatSel] = useState([]);
  const [maxDist, setMaxDist] = useState(DIST_MAX);
  const [maxRuntime, setMaxRuntime] = useState(180);
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState("showtime");

  const [watchlist, setWatchlist] = useState([]);
  const [plan, setPlan] = useState([]);
  const [profile, setProfile] = useState({ genres: [], directors: "", loved: "" });
  const [loaded, setLoaded] = useState(false);

  const [ask, setAsk] = useState("");
  const [asking, setAsking] = useState(false);
  const [aiAnswer, setAiAnswer] = useState(null);
  const [aiFilter, setAiFilter] = useState(null);
  const [showProfile, setShowProfile] = useState(false);
  const listTop = useRef(null);

  // A dashboard left open from Sunday into Monday would otherwise keep
  // showing the finished weekend. Check every 15 minutes.
  useEffect(() => {
    const t = setInterval(() => {
      if (toISO(weekendOf()[0]) !== DAYS[0].iso) window.location.reload();
    }, 15 * 60 * 1000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    (async () => {
      setWatchlist(await load("marquee:watchlist", []));
      setPlan(await load("marquee:plan", []));
      setProfile(await load("marquee:profile", { genres: [], directors: "", loved: "" }));
      setLoaded(true);
    })();
  }, []);

  const toggle = (arr, setArr, v, key) => {
    const next = arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v];
    setArr(next);
    if (key) save(key, next);
  };

  const pickShow = (s) => {
    const exists = plan.find((p) => p.key === s.key);
    const next = exists ? plan.filter((p) => p.key !== s.key) : [...plan, s];
    setPlan(next);
    save("marquee:plan", next);
  };

  /* ---- filtering ---- */
  const dayShowings = useMemo(() => ALL_SHOWINGS.filter((s) => s.day === day), [day]);

  // a showing survives the theater / format / distance filters
  const keepShowing = useMemo(
    () => (s) =>
      (!theaterSel.length || theaterSel.includes(s.theater)) &&
      (!formatSel.length || formatSel.includes(s.format)) &&
      T[s.theater].dist <= maxDist,
    [theaterSel, formatSel, maxDist]
  );

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    const first = {};
    let films = SLATE.filter((f) => {
      const shows = dayShowings.filter((s) => s.filmId === f.id && keepShowing(s));
      if (!shows.length) return false;
      const okGenre = !genreSel.length || f.genres.some((g) => genreSel.includes(g));
      const okRuntime = maxRuntime >= 180 || f.runtime <= maxRuntime;
      const okQuery =
        !q ||
        f.title.toLowerCase().includes(q) ||
        f.director.toLowerCase().includes(q) ||
        f.cast.some((c) => c.toLowerCase().includes(q)) ||
        f.genres.some((g) => g.toLowerCase().includes(q));
      if (okGenre && okRuntime && okQuery) first[f.id] = earliestMins(shows);
      return okGenre && okRuntime && okQuery;
    });
    if (aiFilter) films = films.filter((f) => aiFilter.includes(f.id));
    const cmp = {
      showtime: (a, b) => first[a.id] - first[b.id] || b.popularity - a.popularity,
      popularity: (a, b) => b.popularity - a.popularity,
      critic: (a, b) => (b.critic || -1) - (a.critic || -1),
      audience: (a, b) => (b.audience || -1) - (a.audience || -1),
      release: (a, b) => (a.opened < b.opened ? 1 : -1),
      runtime: (a, b) => a.runtime - b.runtime,
      distance: (a, b) => nearestDist(a, day) - nearestDist(b, day),
    }[sort];
    return [...films].sort(cmp);
  }, [day, genreSel, maxRuntime, query, sort, aiFilter, dayShowings, keepShowing]);

  const stats = useMemo(() => {
    const films = SLATE.filter((f) => f.showings.some((s) => s.split("|")[1] === day));
    const solo = films.filter((f) => filmTheaters(f, day).length === 1).length;
    return { films: films.length, showings: dayShowings.length, solo };
  }, [day, dayShowings]);

  const watchAlerts = SLATE.filter((f) => watchlist.includes(f.id) && f.showings.some((s) => s.split("|")[1] === day));

  /* ---- plan analysis ---- */
  const planByDay = useMemo(() => {
    const g = {};
    plan.forEach((p) => {
      (g[p.day] = g[p.day] || []).push(p);
    });
    Object.values(g).forEach((arr) => arr.sort((a, b) => a.mins - b.mins));
    return g;
  }, [plan]);

  const planIssues = useMemo(() => {
    const out = [];
    Object.entries(planByDay).forEach(([d, arr]) => {
      for (let i = 0; i < arr.length - 1; i++) {
        const a = arr[i], b = arr[i + 1];
        const ends = a.mins + FILM_BY_ID[a.filmId].runtime + 18;
        const gap = b.mins - ends;
        const travel = travelMins(a.theater, b.theater);
        const dl = DAYS.find((x) => x.id === d).label;
        if (gap < 0) {
          out.push({ bad: true, text: `${dl}: ${FILM_BY_ID[a.filmId].title} is still running when ${FILM_BY_ID[b.filmId].title} starts.` });
        } else if (gap < travel) {
          out.push({ bad: true, text: `${dl}: only ${gap} min between ${T[a.theater].short} and ${T[b.theater].short}, and that trip runs about ${travel}.` });
        } else if (arr.length > 1) {
          out.push({ bad: false, text: `${dl}: ${gap} min between films — enough for the ${travel} min trip to ${T[b.theater].short}.` });
        }
      }
    });
    return out;
  }, [planByDay]);

  /* ---- AI ---- */
  const slateForAI = (d) =>
    SLATE.filter((f) => f.showings.some((s) => s.split("|")[1] === d)).map((f) => ({
      id: f.id, title: f.title, year: f.year, director: f.director, cast: f.cast,
      genres: f.genres, runtime: f.runtime, critic: f.critic, audience: f.audience,
      repertory: !!f.repertory, isNew: !!f.isNew, lastWeekend: !!f.lastWeekend, oneNight: !!f.oneNight,
      theaters: filmTheaters(f, d).map((t) => `${t.short} (${t.dist}mi)`),
      formats: filmFormats(f, d),
      times: f.showings.map(parseShowing).filter((s) => s.day === d).map((s) => `${T[s.theater].short} ${fmtTime(s.mins)}`),
    }));

  const runAsk = async (question) => {
    const q = (question ?? ask).trim();
    if (!q) return;
    setAsking(true);
    setAiAnswer(null);
    setAiFilter(null);
    const prompt = `You are the programmer of a personal cinema dashboard for one user in Chicago. Their home is in Logan Square. Below is every film showing on ${DAYS.find((d) => d.id === day).label} ${DAYS.find((d) => d.id === day).date}, 2026 at their six chosen theaters.

TASTE PROFILE
Favorite genres: ${profile.genres.join(", ") || "not set"}
Directors they follow: ${profile.directors || "not set"}
Films they loved: ${profile.loved || "not set"}
On their watchlist: ${watchlist.map((id) => FILM_BY_ID[id]?.title).filter(Boolean).join(", ") || "nothing yet"}

SLATE
${JSON.stringify(slateForAI(day))}

QUESTION: ${q}

Answer in 2-4 sentences, warm and specific, like a friend who works the box office. Name actual titles, theaters and showtimes from the slate. If the taste profile is relevant, connect your picks to it explicitly. Never invent a film or a showtime that is not listed.

Respond with ONLY a JSON object, no markdown fences, no preamble:
{"answer":"...","filmIds":["id","id"]}
filmIds must be ids from the slate that your answer recommends, most relevant first, at most 5. Use an empty array if no specific films apply.`;
    try {
      const res = await fetch("https://api.anthropic.com/v1/messages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model: "claude-sonnet-4-6", max_tokens: 1000, messages: [{ role: "user", content: prompt }] }),
      });
      const data = await res.json();
      const text = data.content.map((c) => c.text || "").join("").replace(/```json|```/g, "").trim();
      const parsed = JSON.parse(text);
      setAiAnswer(parsed.answer);
      if (parsed.filmIds?.length) {
        setAiFilter(parsed.filmIds);
        listTop.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    } catch {
      setAiAnswer("That request did not come back. Try asking again, or narrow the question to one day.");
    }
    setAsking(false);
  };

  const runPicks = () => {
    const pool = SLATE.filter((f) => dayShowings.some((s) => s.filmId === f.id && keepShowing(s)));
    if (!pool.length) { setAiAnswer("Nothing is playing that matches your current filters."); return; }
    const ranked = pool
      .map((f) => ({ f, ...scoreFilm(f, day, profile, watchlist) }))
      .sort((a, b) => b.score - a.score)
      .slice(0, 3);
    const dl = DAYS.find((d) => d.id === day).label;
    const lines = ranked.map(({ f, why }) => {
      const next = dayShowings.filter((s) => s.filmId === f.id && keepShowing(s)).sort((a, b) => a.mins - b.mins)[0];
      const reason = why.length ? why.slice(0, 2).join(", ") : `critics have it at ${f.critic}`;
      return `${f.title} — ${reason}. ${T[next.theater].short}, ${fmtTime(next.mins)}.`;
    });
    const cold = !profile.genres.length && !profile.directors && !profile.loved;
    setAiAnswer(
      (cold ? `No taste profile set yet, so this is ranked on scores and how close the theater is. ` : "") +
        `Three for ${dl}: ` + lines.join(" ")
    );
    setAiFilter(ranked.map((r) => r.f.id));
    listTop.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const runDoubleFeature = () => {
    const shows = dayShowings.filter(keepShowing);
    const pairs = [];
    shows.forEach((a) => {
      shows.forEach((b) => {
        if (a.filmId === b.filmId) return;
        const ends = a.mins + FILM_BY_ID[a.filmId].runtime + 18;
        const gap = b.mins - ends;
        const travel = travelMins(a.theater, b.theater);
        if (gap >= travel + 10 && gap <= 95) {
          const fit =
            scoreFilm(FILM_BY_ID[a.filmId], day, profile, watchlist).score +
            scoreFilm(FILM_BY_ID[b.filmId], day, profile, watchlist).score +
            (a.theater === b.theater ? 25 : 0) +
            (FILM_BY_ID[a.filmId].genres.some((g) => FILM_BY_ID[b.filmId].genres.includes(g)) ? 12 : 0);
          pairs.push({ a, b, gap, travel, fit });
        }
      });
    });
    if (!pairs.length) {
      setAiAnswer("No workable double feature today — nothing lines up with enough room between showtimes.");
      setAiFilter(null);
      return;
    }
    pairs.sort((x, y) => y.fit - x.fit);
    const p = pairs[0];
    const A = FILM_BY_ID[p.a.filmId], B = FILM_BY_ID[p.b.filmId];
    const same = p.a.theater === p.b.theater;
    setAiAnswer(
      `${A.title} at ${T[p.a.theater].short}, ${fmtTime(p.a.mins)}, then ${B.title} at ${T[p.b.theater].short}, ${fmtTime(p.b.mins)}. ` +
        (same
          ? `Same building, so the ${p.gap} minutes in between is all yours — long enough to get a drink and not lose your seat.`
          : `${p.gap} minutes between them and the trip runs about ${p.travel}, so there's room but not much of it.`)
    );
    setAiFilter([p.a.filmId, p.b.filmId]);
    listTop.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const staleHours = FETCHED_AT ? (Date.now() - new Date(FETCHED_AT)) / 3.6e6 : null;
  // During the weekend the listings should be hours old, so 30h means a
  // scrape probably failed. Midweek, a Sunday-morning scrape is simply the
  // most recent one there is — nagging about it every Tuesday trains you
  // to ignore the banner. Only shout when it's genuinely wrong.
  const inWeekend = DAYS.some((d) => d.iso === toISO(new Date()));
  const stale = staleHours !== null && (inWeekend ? staleHours > 30 : staleHours > 168);
  const updatedLabel = FETCHED_AT
    ? new Date(FETCHED_AT).toLocaleString(undefined, { weekday: "short", hour: "numeric", minute: "2-digit" })
    : "never — demo data";

  const seeds = ["What should I see tonight?", "Something under two hours near home", "What's leaving after Sunday?", "Best thing on 35mm or 70mm"];

  return (
    <div className="mq">
      <style>{CSS}</style>
      {slateData.source === "demo" && (
        <div className="mq-fake">
          <div className="mq-fakeIn">
            <b>Demo data</b> — every showtime below is invented for layout purposes. No theater feed is connected.
            Do not use these times to plan a night out; check the theater's own site.
          </div>
        </div>
      )}
      {WEEKEND_OVER && (
        <div className="mq-fake">
          <div className="mq-fakeIn">
            <b>Past weekend</b> — these listings are for {fmtDate(WEEKEND[0])}–{fmtDate(WEEKEND[2])}, which has already
            finished. The next refresh will pull the coming weekend.
          </div>
        </div>
      )}
      {Array.isArray(slateData.partial) && slateData.partial.length > 0 && (
        <div className="mq-fake">
          <div className="mq-fakeIn">
            <b>Partial</b> — this run covers {[...new Set(slateData.films.flatMap((f) => f.showings.map((s) => s.split("|")[0])))].length} of{" "}
            {THEATERS.length} theaters. Missing:{" "}
            {slateData.partial.map((p) => T[p.split(":")[0]]?.short || p.split(":")[0]).join(", ")}.
          </div>
        </div>
      )}
      {stale && (
        <div className="mq-fake">
          <div className="mq-fakeIn">
            <b>Stale</b> — listings last updated {staleHours < 48
              ? `${Math.round(staleHours)} hours`
              : `${Math.round(staleHours / 24)} days`} ago. A scrape may have failed;
            check the theater's site before you go.
          </div>
        </div>
      )}
      <div className="mq-bulbs" />
      <div className="mq-wrap">
        {/* ---------- header ---------- */}
        <header className="mq-head">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", gap: 20, flexWrap: "wrap" }}>
            <div>
              <div className="mq-mark">Marquee</div>
              <div className="mq-sub mq-mono">{`${THEATERS.length} THEATERS · FRI ${fmtDate(WEEKEND[0])} – SUN ${fmtDate(WEEKEND[2])} · CHICAGO`.toUpperCase()}</div>
            </div>
            <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
              <div className="mq-days">
                {DAYS.map((d) => (
                  <button key={d.id} className={`mq-day${day === d.id ? " on" : ""}`} onClick={() => { setDay(d.id); setAiFilter(null); }}>
                    <span className="d">{d.label}</span>
                    <span className="n">{d.date}</span>
                  </button>
                ))}
              </div>
              <button className="mq-btn-ghost" onClick={() => setShowProfile(true)}>Taste profile</button>
            </div>
          </div>
          <div className="mq-stat mq-mono">
            <span><b>{stats.films}</b> films</span>
            <span><b>{stats.showings}</b> showtimes</span>
            <span><b>{stats.solo}</b> at one theater only</span>
            <span><b>{watchlist.length}</b> on your watchlist</span>
            <span>updated <b>{updatedLabel}</b></span>
          </div>
        </header>

        {watchAlerts.length > 0 && (
          <div className="mq-alert">
            <b>On your watchlist and playing {DAYS.find((d) => d.id === day).label}:</b>{" "}
            {watchAlerts.map((f) => f.title).join(", ")}.
          </div>
        )}

        {/* ---------- ask ---------- */}
        <div className="mq-ask">
          <div className="mq-ask-row">
            <button className="mq-btn" onClick={runPicks}>Picks for you</button>
            <button className="mq-btn" onClick={runDoubleFeature}>Build a double feature</button>
            <span className="mq-freetag mq-mono">no API key needed</span>
          </div>
          {aiAnswer && (
            <div className="mq-answer">
              {aiAnswer}
              {aiFilter && (
                <div style={{ marginTop: 10 }}>
                  <button className="mq-btn-ghost" onClick={() => setAiFilter(null)}>Show all films again</button>
                </div>
              )}
            </div>
          )}
          <details className="mq-optional">
            <summary>Ask in plain English — optional, uses the Claude API</summary>
            <div className="mq-ask-row" style={{ marginTop: 12 }}>
              <input
                className="mq-input"
                placeholder="“a good thriller I can walk to”"
                value={ask}
                onChange={(e) => setAsk(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && runAsk()}
              />
              <button className="mq-btn" onClick={() => runAsk()} disabled={asking || !ask.trim()}>
                {asking ? <><span className="mq-spin" />Reading the slate</> : "Ask"}
              </button>
            </div>
            <div className="mq-chiprow">
              {seeds.map((s) => (
                <button key={s} className="mq-seed" onClick={() => { setAsk(s); runAsk(s); }}>{s}</button>
              ))}
            </div>
            <p className="mq-note" style={{ marginTop: 10 }}>
              Everything above this line runs locally and costs nothing. This box is the only part that calls a
              metered API — a fraction of a cent per question. Delete it if you'd rather keep the whole thing free.
            </p>
          </details>
        </div>

        {/* ---------- filters ---------- */}
        <div className="mq-filters">
          <div>
            <div className="mq-flabel">Theater</div>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {THEATERS.map((t) => (
                <button key={t.id} className={`mq-chip${theaterSel.includes(t.id) ? " on" : ""}`} onClick={() => toggle(theaterSel, setTheaterSel, t.id)}>
                  {t.short}<span className="mi">{t.dist}mi</span>
                </button>
              ))}
            </div>
          </div>
          <div>
            <div className="mq-flabel">Genre</div>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {GENRES.map((g) => (
                <button key={g} className={`mq-chip${genreSel.includes(g) ? " on" : ""}`} onClick={() => toggle(genreSel, setGenreSel, g)}>{g}</button>
              ))}
            </div>
          </div>
          <div>
            <div className="mq-flabel">Format</div>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {PREMIUM.map((f) => (
                <button key={f} className={`mq-chip${formatSel.includes(f) ? " on" : ""}`} onClick={() => toggle(formatSel, setFormatSel, f)}>{FORMAT_LABEL[f]}</button>
              ))}
            </div>
          </div>
          <div>
            <div className="mq-flabel">Within <span className="mq-rangeval">{maxDist} mi</span> of home</div>
            <input className="mq-range" type="range" min={DIST_MIN} max={DIST_MAX} step="0.1" value={maxDist} onChange={(e) => setMaxDist(+e.target.value)} />
            <div className="mq-flabel" style={{ marginTop: 14 }}>
              Runtime under <span className="mq-rangeval">{maxRuntime >= 180 ? "any" : fmtRuntime(maxRuntime)}</span>
            </div>
            <input className="mq-range" type="range" min="90" max="180" step="5" value={maxRuntime} onChange={(e) => setMaxRuntime(+e.target.value)} />
          </div>
        </div>

        {/* ---------- toolbar ---------- */}
        <div className="mq-tools" ref={listTop}>
          <div className="mq-count">
            {visible.length} {visible.length === 1 ? "film" : "films"} · {DAYS.find((d) => d.id === day).label} {DAYS.find((d) => d.id === day).date}
            {aiFilter && " · filtered to the picks above"}
            <div style={{ fontSize: 11, letterSpacing: 0, textTransform: "none", marginTop: 4, color: "#6E739B", fontFamily: "'Karla',sans-serif" }}>
              Tap any showtime to add it to your plan. Teal outline means a premium format.
            </div>
          </div>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            <input className="mq-input" style={{ maxWidth: 260 }} placeholder="Search title, director, actor" value={query} onChange={(e) => setQuery(e.target.value)} />
            <select className="mq-select" value={sort} onChange={(e) => setSort(e.target.value)}>
              <option value="showtime">Sort: showtime, earliest first</option>
              <option value="popularity">Sort: most popular</option>
              <option value="critic">Sort: critic score</option>
              <option value="audience">Sort: audience score</option>
              <option value="release">Sort: newest release</option>
              <option value="runtime">Sort: shortest</option>
              <option value="distance">Sort: closest to home</option>
            </select>
          </div>
        </div>

        {/* ---------- list ---------- */}
        {visible.length === 0 ? (
          <div className="mq-empty">
            <div className="mq-h2">Nothing matches yet</div>
            <p>Widen the distance, clear a genre, or search a director you like.</p>
          </div>
        ) : (
          visible.map((f) => {
            const shows = dayShowings.filter((s) => s.filmId === f.id && keepShowing(s));
            const ts = THEATERS.filter((t) => shows.some((s) => s.theater === t.id));
            const fmts = [...new Set(shows.map((s) => s.format))].filter((x) => PREMIUM.includes(x));
            const starred = watchlist.includes(f.id);
            const count = shows.length;
            const firstAt = earliestMins(shows);
            return (
              <article className="mq-card" key={f.id}>
                <Poster film={f} />
                <div>
                  <div className="mq-firstAt mq-mono">First showtime {fmtTime(firstAt)}</div>
                  <h2 className="mq-title">{f.title}</h2>
                  <div className="mq-meta">
                    <em>{f.director}</em> · {f.year} · {f.genres.join(", ")} · {fmtRuntime(f.runtime)}
                  </div>
                  <div className="mq-meta" style={{ marginTop: 2 }}>{f.cast.join(", ")}</div>
                  <div className="mq-badges">
                    {ts.length === 1 && <span className="mq-badge b-only">Only at {ts[0].short}</span>}
                    {f.isNew && <span className="mq-badge b-new">Opened this week</span>}
                    {f.lastWeekend && <span className="mq-badge b-last">Leaves after Sunday</span>}
                    {f.oneNight && <span className="mq-badge b-one">One screening only</span>}
                    {fmts.map((x) => <span key={x} className="mq-badge b-fmt">{FORMAT_LABEL[x]}</span>)}
                  </div>
                  {f.note && <p className="mq-progNote">{f.note}</p>}
                  <p className="mq-blurb">{f.blurb}</p>
                  <div className="mq-scores">
                    <div className="mq-score">
                      <b className={f.critic ? scoreClass(f.critic) : "sc-none"}>{f.critic || "\u2014"}</b><span>critics</span>
                    </div>
                    <div className="mq-score">
                      <b className={f.audience ? scoreClass(f.audience) : "sc-none"}>{f.audience || "\u2014"}</b><span>audience</span>
                    </div>
                    <div className="mq-score mq-mono" style={{ fontSize: 12, color: "var(--dim)" }}>
                      {ts.length} {ts.length === 1 ? "theater" : "theaters"} · {count} showtimes · nearest {nearestDist(f, day)} mi
                    </div>
                  </div>
                  <div className="mq-cardtools">
                    <button className={`mq-star${starred ? " on" : ""}`} onClick={() => toggle(watchlist, setWatchlist, f.id, "marquee:watchlist")}>
                      {starred ? "★ On your watchlist" : "☆ Watch for this"}
                    </button>
                  </div>
                  <Showtimes film={f} day={day} picked={plan.map((p) => p.key)} onPick={pickShow} keep={keepShowing} />
                </div>
              </article>
            );
          })
        )}

        <footer className="mq-foot">
          {slateData.source === "demo" ? (
            <p className="mq-note">Sample listings. Not real showtimes — check the theater's own site.</p>
          ) : (
            <p className="mq-note">
              Showtimes scraped from public listings for Music Box, Gene Siskel Film Center and AMC River East 21.
              Always worth confirming with the theater before you travel.
            </p>
          )}
          {/* TMDB's terms require crediting them as the source of the data
              and images, and require making clear they haven't endorsed this. */}
          {SLATE.some((f) => f.posterUrl || f.director) && (
            <p className="mq-note" style={{ marginTop: 8 }}>
              Film metadata and poster art from{" "}
              <a className="mq-link" href="https://www.themoviedb.org/" target="_blank" rel="noopener noreferrer">
                The Movie Database (TMDB)
              </a>
              . This product uses the TMDB API but is not endorsed or certified by TMDB.
            </p>
          )}
        </footer>
      </div>

      {/* ---------- plan tray ---------- */}
      {plan.length > 0 && (
        <div className="mq-tray">
          <div className="mq-trayIn">
            <div className="mq-trayHead">
              <div className="mq-trayTitle">Your plan · {plan.length} {plan.length === 1 ? "showtime" : "showtimes"}</div>
              <button className="mq-btn-ghost" onClick={() => { setPlan([]); save("marquee:plan", []); }}>Clear plan</button>
            </div>
            <div className="mq-plan">
              {plan
                .slice()
                .sort((a, b) => DAYS.findIndex((d) => d.id === a.day) - DAYS.findIndex((d) => d.id === b.day) || a.mins - b.mins)
                .map((p) => (
                  <div className="mq-planItem" key={p.key}>
                    <div className="t">{FILM_BY_ID[p.filmId].title}</div>
                    <div className="d">
                      {DAYS.find((d) => d.id === p.day).label} {fmtTime(p.mins)} · {T[p.theater].short}
                      {PREMIUM.includes(p.format) ? ` · ${FORMAT_LABEL[p.format]}` : ""}
                    </div>
                    <button className="mq-btn-ghost" style={{ marginTop: 8, padding: "4px 9px", fontSize: 11 }} onClick={() => pickShow(p)}>Remove</button>
                  </div>
                ))}
            </div>
            {planIssues.slice(0, 3).map((i, n) => (
              <div key={n} className={i.bad ? "mq-warn" : "mq-ok"}>{i.bad ? "⚠ " : "✓ "}{i.text}</div>
            ))}
          </div>
        </div>
      )}

      {/* ---------- profile modal ---------- */}
      {showProfile && (
        <div className="mq-modalbg" onClick={() => setShowProfile(false)}>
          <div className="mq-modal" onClick={(e) => e.stopPropagation()}>
            <div className="mq-h2" style={{ color: "var(--bulb)" }}>Taste profile</div>
            <p className="mq-note" style={{ marginTop: 8 }}>
              This is what the dashboard uses when you ask it something. It saves between visits.
            </p>
            <div className="mq-flabel" style={{ marginTop: 20 }}>Genres you reach for</div>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {GENRES.map((g) => (
                <button
                  key={g}
                  className={`mq-chip${profile.genres.includes(g) ? " on" : ""}`}
                  onClick={() => {
                    const genres = profile.genres.includes(g) ? profile.genres.filter((x) => x !== g) : [...profile.genres, g];
                    const next = { ...profile, genres };
                    setProfile(next);
                    save("marquee:profile", next);
                  }}
                >
                  {g}
                </button>
              ))}
            </div>
            <div className="mq-flabel" style={{ marginTop: 20 }}>Directors you follow</div>
            <input
              className="mq-input" style={{ width: "100%" }} placeholder="Wong Kar-wai, Agnès Varda, Denis Villeneuve"
              value={profile.directors}
              onChange={(e) => { const next = { ...profile, directors: e.target.value }; setProfile(next); save("marquee:profile", next); }}
            />
            <div className="mq-flabel" style={{ marginTop: 20 }}>Films you loved</div>
            <input
              className="mq-input" style={{ width: "100%" }} placeholder="Arrival, Chungking Express, Heat"
              value={profile.loved}
              onChange={(e) => { const next = { ...profile, loved: e.target.value }; setProfile(next); save("marquee:profile", next); }}
            />
            <div style={{ marginTop: 24, display: "flex", justifyContent: "flex-end" }}>
              <button className="mq-btn" onClick={() => setShowProfile(false)}>Done</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------
   DATA CONTRACT — what your scraper needs to produce per film:

   { id, title, year, runtime (minutes), director, cast[], genres[],
     critic, audience, popularity, opened ("YYYY-MM-DD"), blurb,
     posterUrl?, isNew?, lastWeekend?, oneNight?, repertory?,
     showings: ["theaterId|day|HH:MM|format", ...] }

   posterUrl  → optional. Set it and the card renders that image instead
                of the generated art. TMDB gives you a poster_path on the
                movie record; the full URL is the image base
                (https://image.tmdb.org/t/p/) + a size (w342 suits this
                card) + the path. TMDB requires attribution and forbids
                implying they endorse you — read their terms before
                shipping. AMC's Media API also returns poster art for
                current releases, licensed for use alongside their
                showtimes.

   theaterId  → one of: musicbox, siskel, rivereast
   day        → fri | sat | sun
   HH:MM      → 24h; use 24:00+ for after-midnight shows
   format     → imax | dolby | 70mm | 35mm | 3d | 4k | standard

   Dedupe on title + year across theaters, then merge each theater's
   times into the one showings array. That merge is what makes the
   comparison ruler work.
------------------------------------------------------------------- */
