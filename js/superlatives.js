/*
  js/superlatives.js

  Fetches superlatives.json, rivalry_lanes.json, and
  draft_day_profiler.json to render four sections:
    1. Season Records  - category banners (14 categories, too many to
       show flat) -> one leaderboard at a time. THREE entry shapes
       exist within this one section (see SEASON_CATEGORIES below).
    2. Career Leaders   - all 5 categories shown at once (small enough)
    3. Rivalry Records   - all 5 categories, two-sided "vs" entries
    4. Draft Records      - all 5 categories, mixed entry shapes
       (some are player-based picks, some are manager retention stats)

  Field names below match each file exactly as produced by
  compute_superlatives.py, compute_rivalries.py, and
  compute_draft_day_profiler.py.
*/

const SUPERLATIVES_PATH = "data/derived/superlatives.json";
const RIVALRY_PATH = "data/derived/rivalry_lanes.json";
const DRAFT_PATH = "data/derived/draft_day_profiler.json";

let superlativesData = null;
let rivalryData = null;
let draftData = null;

async function init() {
  const [sRes, rRes, dRes] = await Promise.all([
    fetch(SUPERLATIVES_PATH),
    fetch(RIVALRY_PATH),
    fetch(DRAFT_PATH),
  ]);

  if (!sRes.ok || !rRes.ok || !dRes.ok) {
    console.error("Failed to load one or more superlatives data sources");
    return;
  }

  superlativesData = await sRes.json();
  rivalryData = await rRes.json();
  draftData = await dRes.json();

  renderSeasonRecords();
  renderCareerLeaders();
  renderRivalryRecords();
  renderDraftRecords();
}

function showSection(id, el) {
  document.querySelectorAll(".section-tab").forEach(t => t.classList.remove("active"));
  document.querySelectorAll(".section-content").forEach(s => s.classList.remove("active"));
  el.classList.add("active");
  document.getElementById("section-" + id).classList.add("active");
}

/* ===========================================================
   SEASON RECORDS - category banners, 3 distinct entry shapes:
   "single"  = season-long stat, one manager (e.g. highest_points_for)
   "weekly"  = single-week stat, one manager + week (e.g. highest_single_week_score)
   "matchup" = two-manager game (e.g. biggest_blowout, closest_game)
   =========================================================== */

const SEASON_CATEGORIES = [
  { key: "highest_points_for", label: "HIGHEST PTS FOR", type: "single" },
  { key: "lowest_points_for", label: "LOWEST PTS FOR", type: "single" },
  { key: "highest_points_against", label: "HIGHEST PTS AGAINST", type: "single" },
  { key: "lowest_points_against", label: "LOWEST PTS AGAINST", type: "single" },
  { key: "best_record", label: "BEST RECORD", type: "single" },
  { key: "worst_record", label: "WORST RECORD", type: "single" },
  { key: "longest_win_streak", label: "LONGEST WIN STREAK", type: "single" },
  { key: "longest_losing_streak", label: "LONGEST LOSE STREAK", type: "single" },
  { key: "most_trades_season", label: "MOST TRADES (SEASON)", type: "single" },
  { key: "most_acquisitions_season", label: "MOST ACQUISITIONS", type: "single" },
  { key: "highest_single_week_score", label: "HIGHEST WEEK SCORE", type: "weekly" },
  { key: "lowest_single_week_score", label: "LOWEST WEEK SCORE", type: "weekly" },
  { key: "biggest_blowout", label: "BIGGEST BLOWOUT", type: "matchup" },
  { key: "closest_game", label: "CLOSEST GAME", type: "matchup" },
];

function renderSeasonEntry(entry, type) {
  if (type === "single") {
    const recordNote = entry.record ? ` &middot; ${entry.record}` : "";
    return `
      <div class="stat-entry">
        <div class="stat-info">
          <div class="stat-name">${entry.owner_name}</div>
          <div class="stat-meta">${entry.year} &middot; ${entry.team_name}${recordNote}</div>
        </div>
        <span class="stat-value">${formatValue(entry.value)}</span>
      </div>
    `;
  }
  if (type === "weekly") {
    return `
      <div class="stat-entry">
        <div class="stat-info">
          <div class="stat-name">${entry.owner_name}</div>
          <div class="stat-meta">${entry.year} &middot; Week ${entry.week}</div>
        </div>
        <span class="stat-value">${formatValue(entry.value)}</span>
      </div>
    `;
  }
  // matchup type
  return `
    <div class="stat-entry">
      <div class="stat-info">
        <div class="stat-name">${entry.matchup}</div>
        <div class="stat-meta">${entry.year} &middot; Week ${entry.week}</div>
      </div>
      <span class="stat-value">${formatValue(entry.value)}</span>
    </div>
  `;
}

function formatValue(v) {
  return typeof v === "number" ? v.toFixed(1) : v;
}

function renderSeasonRecords() {
  const banners = document.getElementById("season-banners");
  const boards = document.getElementById("season-boards");
  const records = superlativesData.season_records;

  SEASON_CATEGORIES.forEach((cat, i) => {
    const entries = records[cat.key] || [];

    const banner = document.createElement("div");
    banner.className = "category-banner" + (i === 0 ? " active" : "");
    banner.textContent = cat.label;
    banner.onclick = () => {
      document.querySelectorAll("#season-banners .category-banner").forEach(b => b.classList.remove("active"));
      document.querySelectorAll("#season-boards .category-board").forEach(b => b.classList.remove("active"));
      banner.classList.add("active");
      document.getElementById("board-" + cat.key).classList.add("active");
    };
    banners.appendChild(banner);

    const board = document.createElement("div");
    board.className = "category-board" + (i === 0 ? " active" : "");
    board.id = "board-" + cat.key;
    board.innerHTML = `<div class="board-title">— ${cat.label} —</div>` +
      (entries.length
        ? entries.map(e => renderSeasonEntry(e, cat.type)).join("")
        : `<p class="stat-meta">No data available.</p>`);
    boards.appendChild(board);
  });
}

/* ===========================================================
   CAREER LEADERS - all 5 shown at once, each pulling a
   DIFFERENT field as its "value" from the same rich manager object
   =========================================================== */

const CAREER_CATEGORIES = [
  { key: "most_championships", label: "🏆 MOST CHAMPIONSHIPS", valueField: "championships", format: v => v },
  { key: "best_career_win_pct", label: "📈 BEST CAREER WIN %", valueField: "win_pct", format: v => (v * 100).toFixed(1) + "%" },
  { key: "worst_career_win_pct", label: "📉 WORST CAREER WIN %", valueField: "win_pct", format: v => (v * 100).toFixed(1) + "%" },
  { key: "most_trades_career", label: "🔄 MOST CAREER TRADES", valueField: "trades", format: v => v },
  { key: "most_last_place_finishes", label: "💀 MOST LAST-PLACE FINISHES", valueField: "last_place_finishes", format: v => v },
];

function renderCareerLeaders() {
  const container = document.getElementById("career-boards");
  const leaders = superlativesData.career_records.leaders;

  container.innerHTML = CAREER_CATEGORIES.map(cat => {
    const entries = leaders[cat.key] || [];
    const rows = entries.map(e => `
      <div class="stat-entry">
        <div class="stat-info">
          <div class="stat-name">${e.owner_name}</div>
          <div class="stat-meta">${e.wins}-${e.losses}-${e.ties}</div>
        </div>
        <span class="stat-value">${cat.format(e[cat.valueField])}</span>
      </div>
    `).join("");

    return `
      <div class="mini-board">
        <div class="mini-board-title">${cat.label}</div>
        ${rows || '<p class="stat-meta">No data available.</p>'}
      </div>
    `;
  }).join("");
}

/* ===========================================================
   RIVALRY RECORDS - two entry shapes:
   "pair"  = a whole rivalry (manager_a/manager_b with a win/loss record)
   "game"  = one single game between two managers
   =========================================================== */

const RIVALRY_CATEGORIES = [
  { key: "most_lopsided_rivalries", label: "⚔️ MOST LOPSIDED RIVALRY", type: "pair" },
  { key: "closest_rivalries", label: "🤝 CLOSEST RIVALRY", type: "pair" },
  { key: "longest_running_rivalries", label: "📅 LONGEST-RUNNING RIVALRY", type: "pair" },
  { key: "biggest_single_game_blowouts", label: "💥 BIGGEST SINGLE-GAME BLOWOUT", type: "game" },
  { key: "closest_single_games", label: "🔥 CLOSEST SINGLE GAME", type: "game" },
];

function renderRivalryPairEntry(e) {
  const aClass = e.wins_a > e.wins_b ? "winning-side" : e.wins_a < e.wins_b ? "losing-side" : "tied-side";
  const bClass = e.wins_b > e.wins_a ? "winning-side" : e.wins_b < e.wins_a ? "losing-side" : "tied-side";
  return `
    <div class="rivalry-entry">
      <div class="rivalry-vs">
        <span class="${aClass}">${e.manager_a} (${e.wins_a})</span>
        <span class="vs-mark">VS</span>
        <span class="${bClass}">${e.manager_b} (${e.wins_b})</span>
      </div>
      <div class="rivalry-meta">${e.games_played} GAMES ALL-TIME${e.ties ? ` &middot; ${e.ties} TIE${e.ties === 1 ? "" : "S"}` : ""}</div>
    </div>
  `;
}

function renderRivalryGameEntry(e) {
  const aIsWinner = e.winner === e.manager_a;
  const bIsWinner = e.winner === e.manager_b;
  return `
    <div class="rivalry-entry">
      <div class="rivalry-vs">
        <span class="${aIsWinner ? "winning-side" : "losing-side"}">${e.manager_a}</span>
        <span class="vs-mark">VS</span>
        <span class="${bIsWinner ? "winning-side" : "losing-side"}">${e.manager_b}</span>
      </div>
      <div class="rivalry-meta">${e.year} &middot; Week ${e.week}${e.is_playoff ? " &middot; PLAYOFFS" : ""} &middot; MARGIN: ${e.margin.toFixed(1)}</div>
    </div>
  `;
}

function renderRivalryRecords() {
  const container = document.getElementById("rivalry-boards");
  const supers = rivalryData.superlatives;

  container.innerHTML = RIVALRY_CATEGORIES.map(cat => {
    const entries = supers[cat.key] || [];
    const rows = entries.map(e => cat.type === "pair" ? renderRivalryPairEntry(e) : renderRivalryGameEntry(e)).join("");

    return `
      <div class="mini-board">
        <div class="mini-board-title">${cat.label}</div>
        ${rows || '<p class="stat-meta">No data available.</p>'}
      </div>
    `;
  }).join("");
}

/* ===========================================================
   DRAFT RECORDS - two entry shapes:
   "pick"    = a single draft pick (player-based)
   "manager" = a manager-level retention stat (no player involved)
   =========================================================== */

const DRAFT_CATEGORIES = [
  { key: "most_loyal_managers", label: "🔒 MOST LOYAL MANAGERS (RETENTION)", type: "manager", valueField: "retention_rate", format: v => (v * 100).toFixed(1) + "%" },
  { key: "biggest_roster_churners", label: "🔀 BIGGEST ROSTER CHURNERS", type: "manager", valueField: "retention_rate", format: v => (v * 100).toFixed(1) + "%" },
  { key: "best_picks_in_league_history", label: "⭐ BEST PICKS IN LEAGUE HISTORY", type: "pick" },
  { key: "worst_busts_in_league_history", label: "✕ WORST BUSTS IN LEAGUE HISTORY", type: "pick" },
  { key: "best_qb_campaigns_in_league_history", label: "⚡ BEST QB CAMPAIGNS EVER", type: "pick" },
];

function renderDraftPickEntry(p) {
  return `
    <div class="draft-entry">
      <div class="draft-player">${p.player_name} (${p.position})</div>
      <div class="draft-drafted-by">Drafted by ${p.drafted_by_name} &middot; Round ${p.round_num}, Pick ${p.round_pick} &middot; ${p.year}</div>
      <div class="draft-stat-row"><span>${p.value_score != null ? "VALUE SCORE: " + p.value_score.toFixed(1) : ""}</span><span class="draft-points">${p.total_points.toFixed(2)} PTS</span></div>
    </div>
  `;
}

function renderDraftManagerEntry(m, cat) {
  return `
    <div class="draft-manager-entry">
      <span class="draft-manager-name">${m.owner_name}</span>
      <span class="draft-manager-stat">${cat.format(m[cat.valueField])}</span>
    </div>
  `;
}

function renderDraftRecords() {
  const container = document.getElementById("draft-boards");
  const leaders = draftData.league_leaders;

  container.innerHTML = DRAFT_CATEGORIES.map(cat => {
    const entries = leaders[cat.key] || [];
    const rows = entries.map(e => cat.type === "pick" ? renderDraftPickEntry(e) : renderDraftManagerEntry(e, cat)).join("");

    return `
      <div class="mini-board">
        <div class="mini-board-title">${cat.label}</div>
        ${rows || '<p class="stat-meta">No data available.</p>'}
      </div>
    `;
  }).join("");
}

document.addEventListener("DOMContentLoaded", init);
