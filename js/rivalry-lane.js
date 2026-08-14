// Rivalry Lane JavaScript

/*
  js/rivalry-lane.js

  Fetches data/derived/rivalry_lanes.json (head-to-head matchup data)
  and data/derived/manager_profiles.json (for status/canonical_id
  resolution, since rivalry_lanes.json only stores display names).

  Field names below match rivalry_lanes.json exactly as produced by
  compute_rivalries.py. Each game object's per-side keys are DYNAMIC -
  they're the canonical_id of whichever two managers are in that
  matchup (e.g. "yannis_bi", "justin_lee") - not fixed field names.
*/

const RIVALRY_DATA_PATH = "data/derived/rivalry_lanes.json";
const PROFILES_DATA_PATH = "data/derived/manager_profiles.json";
const PHOTO_PATH = (canonicalId) => `images/rivalry_lane/${canonicalId}.jpg`;

let picks = [];
let rivalryData = null;
let managerProfiles = null;
let nameToCanonicalId = {};

/*
  Same graceful-fallback avatar pattern as Meet Your Managers, but
  reading from its OWN photo folder (images/rivalry_lane/) since this
  page may use different photos than the Managers page.
*/
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
  const [rivalryRes, profilesRes] = await Promise.all([
    fetch(RIVALRY_DATA_PATH),
    fetch(PROFILES_DATA_PATH),
  ]);

  if (!rivalryRes.ok || !profilesRes.ok) {
    console.error("Failed to load rivalry or manager data");
    return;
  }

  rivalryData = await rivalryRes.json();
  managerProfiles = await profilesRes.json();

  // Build a display-name -> canonical_id lookup, since rivalry_lanes.json
  // stores names but we need canonical_id for status + photo lookups
  Object.entries(managerProfiles).forEach(([canonicalId, m]) => {
    nameToCanonicalId[m.owner_name] = canonicalId;
  });

  renderGrid();
}

function renderGrid() {
  const grid = document.getElementById("grid");
  // All managers regardless of status, per requirement
  Object.entries(managerProfiles).forEach(([canonicalId, m]) => {
    const card = document.createElement("div");
    card.className = "card" + (m.status === "retired" ? " retired" : "");
    card.dataset.name = m.owner_name;
    card.dataset.canonicalId = canonicalId;
    card.onclick = () => pick(card);

    card.innerHTML = `
      ${renderAvatar(canonicalId, "avatar-placeholder")}
      <div class="card-name">${m.owner_name.toUpperCase()}</div>
      <div class="card-status">${m.status.toUpperCase()}</div>
    `;
    grid.appendChild(card);
  });
}

function pick(el) {
  if (picks.length >= 2) return;

  const name = el.dataset.name;
  picks.push(name);
  el.classList.add(picks.length === 1 ? "picked1" : "picked2");

  if (picks.length === 1) {
    document.getElementById("instruction").textContent =
      "NOW PICK THEIR OPPONENT";
  } else {
    showVs();
  }
}

function findMatchup(nameA, nameB) {
  return rivalryData.matchups.find(
    (m) =>
      (m.manager_a === nameA && m.manager_b === nameB) ||
      (m.manager_a === nameB && m.manager_b === nameA),
  );
}

function showVs() {
  const [pickedA, pickedB] = picks;
  const matchup = findMatchup(pickedA, pickedB);
  const cidA = nameToCanonicalId[pickedA];
  const cidB = nameToCanonicalId[pickedB];

  document.getElementById("side-avatar-a").innerHTML = renderAvatar(
    cidA,
    "side-avatar-placeholder",
  );
  document.getElementById("side-avatar-b").innerHTML = renderAvatar(
    cidB,
    "side-avatar-placeholder",
  );
  document.getElementById("name1").textContent = pickedA.toUpperCase();
  document.getElementById("name2").textContent = pickedB.toUpperCase();
  document.getElementById("status1").textContent =
    managerProfiles[cidA].status.toUpperCase();
  document.getElementById("status2").textContent =
    managerProfiles[cidB].status.toUpperCase();

  if (!matchup) {
    // These two have genuinely never played each other - real possibility,
    // not an error, given league size grew over time.
    document.getElementById("record-summary").textContent =
      "NO HISTORY — THESE TWO HAVE NEVER MET";
    document.getElementById("health-bars").style.display = "none";
    document.getElementById("rivalry-stats").style.display = "none";
    document.getElementById("rounds-list").innerHTML = "";
    document.getElementById("vs-screen").classList.add("open");
    document.getElementById("vs-screen").scrollIntoView({ behavior: "smooth" });
    return;
  }

  // manager_a/manager_b in the JSON may not match the ORDER the user
  // picked them in - resolve which side is which explicitly.
  const aIsManagerA = matchup.manager_a === pickedA;
  const winsA = aIsManagerA ? matchup.wins_a : matchup.wins_b;
  const winsB = aIsManagerA ? matchup.wins_b : matchup.wins_a;
  const pointsA = aIsManagerA ? matchup.points_a : matchup.points_b;
  const pointsB = aIsManagerA ? matchup.points_b : matchup.points_a;

  document.getElementById("health-bars").style.display = "block";
  document.getElementById("rivalry-stats").style.display = "grid";

  const totalGames = matchup.games_played;
  const pctA = totalGames ? (winsA / totalGames) * 100 : 50;
  const pctB = totalGames ? (winsB / totalGames) * 100 : 50;
  document.getElementById("health-fill-a").style.width = pctA + "%";
  document.getElementById("health-fill-b").style.width = pctB + "%";
  document.getElementById("health-count-a").textContent = winsA;
  document.getElementById("health-count-b").textContent = winsB;

  document.getElementById("record-summary").textContent =
    `${totalGames} ALL-TIME MEETING${totalGames === 1 ? "" : "S"}${matchup.ties ? ` · ${matchup.ties} TIE${matchup.ties === 1 ? "" : "S"}` : ""}`;

  document.getElementById("stat-pf-a").textContent = pointsA.toLocaleString();
  document.getElementById("stat-pf-b").textContent = pointsB.toLocaleString();
  document.getElementById("stat-winpct").textContent =
    (matchup.win_pct_a * 100).toFixed(1) +
    "% / " +
    ((1 - matchup.win_pct_a - matchup.ties / totalGames) * 100).toFixed(1) +
    "%";

  const list = document.getElementById("rounds-list");
  list.innerHTML = "";
  const sortedGames = [...matchup.games].sort(
    (g1, g2) => g1.year - g2.year || g1.week - g2.week,
  );

  sortedGames.forEach((g) => {
    const sideA = g[cidA];
    const sideB = g[cidB];
    if (!sideA || !sideB) return; // defensive - shouldn't happen but don't crash if it does

    const row = document.createElement("div");
    row.className = "round" + (g.is_playoff ? " playoff" : "");
    const playoffTag = g.is_playoff
      ? `<span class="playoff-tag">[${g.matchup_type.replace(/_/g, " ")}]</span>`
      : "";
    row.innerHTML = `
      <span>${g.year} &middot; Wk ${g.week} ${playoffTag}</span>
      <span>${sideA.score} — ${sideB.score} &middot; ${g.winner.toUpperCase()} WINS</span>
    `;
    list.appendChild(row);
  });

  document.getElementById("vs-screen").classList.add("open");
  document.getElementById("vs-screen").scrollIntoView({ behavior: "smooth" });
}

function resetPicks() {
  picks = [];
  document
    .querySelectorAll(".card")
    .forEach((c) => c.classList.remove("picked1", "picked2"));
  document.getElementById("vs-screen").classList.remove("open");
  document.getElementById("instruction").textContent =
    "PICK TWO MANAGERS TO SEE THEIR HEAD-TO-HEAD";
}

document.addEventListener("DOMContentLoaded", init);
