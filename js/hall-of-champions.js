/*
  js/hall-of-champions.js

  Fetches data/derived/hall_of_champions.json (champion + top performers
  per year) and data/derived/playoffs.json (full bracket data), and
  reconstructs each champion's WINNERS_BRACKET path - every game they
  played that postseason, in order, not just the final result.

  Field names below match both files exactly as produced by
  compute_hall_of_champions.py and compute_playoffs.py.
*/

const HALL_DATA_PATH = "data/derived/hall_of_champions.json";
const PLAYOFFS_DATA_PATH = "data/derived/playoffs.json";
const PHOTO_PATH = (canonicalId) => `images/managers/${canonicalId}.jpg`;

let hallData = null;
let playoffsData = null;

function renderAvatar(canonicalId, sizeClass) {
  return `
    <div class="${sizeClass}" data-manager-id="${canonicalId}">
      <img
        src="${PHOTO_PATH(canonicalId)}"
        alt=""
        style="display:none; width:100%; height:100%; object-fit:cover;"
        onload="this.style.display='block'; this.nextElementSibling.style.display='none';"
        onerror="this.style.display='none';"
      >
      <span class="placeholder-text">PHOTO</span>
    </div>
  `;
}

async function init() {
  const [hallRes, playoffsRes] = await Promise.all([
    fetch(HALL_DATA_PATH),
    fetch(PLAYOFFS_DATA_PATH),
  ]);

  if (!hallRes.ok || !playoffsRes.ok) {
    console.error("Failed to load hall of champions or playoffs data");
    return;
  }

  hallData = await hallRes.json();
  playoffsData = await playoffsRes.json();

  renderSlots();
}

function renderSlots() {
  const slotsEl = document.getElementById("slots");

  // Chronological order, Slot 1 = league's founding year - hall_of_champions.json
  // is already sorted this way by compute_hall_of_champions.py, but sort
  // defensively in case that ever changes.
  const sorted = [...hallData].sort((a, b) => a.year - b.year);

  sorted.forEach((entry, i) => {
    const slot = document.createElement("div");
    slot.className = "slot";
    slot.id = `slot-${entry.year}`;
    slot.onclick = () => selectSlot(entry.year, slot);

    slot.innerHTML = `
      <div class="slot-left">
        <span class="slot-num">SLOT ${String(i + 1).padStart(2, "0")}</span>
        <div class="slot-info">
          <div class="champ">${entry.owners_display.toUpperCase()}</div>
          <div class="year">${entry.year} &middot; ${entry.record}</div>
        </div>
      </div>
      <span class="slot-arrow">▸</span>
    `;
    slotsEl.appendChild(slot);
  });
}

/*
  Reconstructs a champion's full WINNERS_BRACKET path for a given year:
  every game they appear in (as home or away), sorted by week. Since
  they won the championship, they should have won every game found
  here - this is naturally the case, not something forced.
*/
function getChampionBracketPath(year, championName) {
  const bracket = playoffsData[String(year)]?.WINNERS_BRACKET || [];
  return bracket
    .filter(g => g.home_owners_display === championName || g.away_owners_display === championName)
    .sort((a, b) => a.week - b.week);
}

function roundLabel(index, total) {
  // Label rounds relative to the FINAL, since bracket length varies by
  // league size across years (2018 had 2 rounds, most years have 3).
  const roundsFromEnd = total - index;
  if (roundsFromEnd === 1) return "FINAL";
  if (roundsFromEnd === 2) return "SEMIFINAL";
  return "QUARTERFINAL";
}

function selectSlot(year, slotEl) {
  document.querySelectorAll(".slot").forEach(s => s.classList.remove("selected"));
  slotEl.classList.add("selected");

  const entry = hallData.find(e => e.year === year);
  const cid = entry.owners[0].canonical_id;

  document.getElementById("d-avatar").innerHTML = renderAvatar(cid, "detail-avatar-placeholder");
  document.getElementById("d-title").textContent = `${entry.year} CHAMPION — ${entry.owners_display.toUpperCase()}`;
  document.getElementById("d-team").textContent = `"${entry.team_name}"`;

  document.getElementById("d-record").textContent = entry.record;
  document.getElementById("d-pf").textContent = entry.points_for.toLocaleString();
  document.getElementById("d-pa").textContent = entry.points_against.toLocaleString();

  const perfList = document.getElementById("performers-list");
  perfList.innerHTML = entry.top_performers.map((p, i) => `
    <div class="performer">
      <span><span class="rank">${i + 1}.</span> ${p.player_name} (${p.position})</span>
      <span class="pts">${p.total_points.toFixed(2)} PTS</span>
    </div>
  `).join("");

  const games = getChampionBracketPath(entry.year, entry.owners_display);
  const bracketEl = document.getElementById("bracket");

  if (games.length === 0) {
    bracketEl.innerHTML = `<p style="font-family:monospace; font-size:11px; color:#888;">No bracket data found for this season.</p>`;
  } else {
    bracketEl.innerHTML = games.map((g, i) => {
      const champIsHome = g.home_owners_display === entry.owners_display;
      const oppName = champIsHome ? g.away_owners_display : g.home_owners_display;
      const oppSeed = champIsHome ? g.away_seed : g.home_seed;
      const champSeed = champIsHome ? g.home_seed : g.away_seed;
      const champScore = champIsHome ? g.home_score : g.away_score;

      // A bracket bye: the opponent side is empty (no team played that
      // round). Confirmed real in this data - e.g. the top remaining
      // seed getting a first-round bye in years with an odd playoff
      // count. Show this honestly instead of a broken "beat null 0".
      if (!oppName) {
        return `
          <div class="bracket-round">
            <div class="bracket-round-label">${roundLabel(i, games.length)} &middot; WEEK ${g.week}</div>
            <div class="bracket-game">
              <span class="side"><span class="seed">${champSeed}</span> <span class="winner-name">${entry.owners_display.toUpperCase()}</span></span>
              <span class="score">BYE — ADVANCES AUTOMATICALLY</span>
            </div>
          </div>
        `;
      }

      const oppScore = champIsHome ? g.away_score : g.home_score;

      return `
        <div class="bracket-round">
          <div class="bracket-round-label">${roundLabel(i, games.length)} &middot; WEEK ${g.week}</div>
          <div class="bracket-game">
            <span class="side"><span class="seed">${champSeed}</span> <span class="winner-name">${entry.owners_display.toUpperCase()}</span></span>
            <span class="score">${champScore} — ${oppScore}</span>
            <span class="side"><span class="seed">${oppSeed}</span> <span class="loser-name">${oppName.toUpperCase()}</span></span>
          </div>
        </div>
      `;
    }).join("");
  }

  const detailEl = document.getElementById("detail");
  detailEl.classList.add("open");
  detailEl.scrollIntoView({ behavior: "smooth" });
}

function closeDetail() {
  document.getElementById("detail").classList.remove("open");
  document.querySelectorAll(".slot").forEach(s => s.classList.remove("selected"));
}

document.addEventListener("DOMContentLoaded", init);
