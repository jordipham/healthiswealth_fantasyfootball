// JAVASCRIPT FOR MANAGER PROFILES PAGE

/*
  js/managers.js

  Fetches data/derived/manager_profiles.json and renders:
    - An ACTIVE MANAGERS grid
    - A RETIRED MANAGERS grid
    - An expandable full profile when a card is clicked

  Field names below match manager_profiles.json exactly as produced
  by compute_manager_profiles.py - if that script's output shape ever
  changes, update the field references here to match.
*/

const DATA_PATH = "data/derived/manager_profiles.json";
const PHOTO_PATH = (canonicalId) => `images/managers/${canonicalId}.jpg`;

/*
  Renders an avatar box that tries to load a real photo for this
  manager. If images/managers/<canonical_id>.jpg doesn't exist yet,
  it fails silently and the "PHOTO" placeholder box stays visible -
  no broken-image icon, no console error shown to the user. This lets
  you add photos gradually, one manager at a time, without anything
  looking broken in the meantime.
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

async function loadManagers() {
  const res = await fetch(DATA_PATH);
  if (!res.ok) {
    console.error("Failed to load manager_profiles.json:", res.status);
    return;
  }
  const data = await res.json();
  renderGrids(data);
}

function renderGrids(data) {
  const activeGrid = document.getElementById("active-grid");
  const retiredGrid = document.getElementById("retired-grid");

  // canonical_id is the object key in manager_profiles.json (e.g. "jonathan_bi")
  const entries = Object.entries(data);

  entries.forEach(([canonicalId, manager]) => {
    const card = buildCard(canonicalId, manager);
    if (manager.status === "retired") {
      retiredGrid.appendChild(card);
    } else {
      activeGrid.appendChild(card);
    }
  });
}

function buildCard(canonicalId, manager) {
  const card = document.createElement("div");
  card.className = "card" + (manager.status === "retired" ? " retired" : "");
  card.onclick = () => showProfile(canonicalId, manager);

  const ringCount = manager.career.championships || 0;
  const tag =
    ringCount > 0
      ? "🏆".repeat(ringCount)
      : manager.status === "retired"
        ? "RETIRED"
        : "—";

  card.innerHTML = `
    ${renderAvatar(canonicalId, "avatar-placeholder")}
    <div class="card-name">${manager.owner_name.toUpperCase()}</div>
    <div class="card-tag">${tag}</div>
  `;
  return card;
}

function showProfile(canonicalId, manager) {
  const c = manager.career;

  document.getElementById("p-avatar-wrap").innerHTML = renderAvatar(
    canonicalId,
    "profile-avatar-placeholder",
  );
  document.getElementById("p-name").textContent =
    manager.owner_name.toUpperCase();
  document.getElementById("p-status").textContent =
    manager.status.toUpperCase();

  const ringsEl = document.getElementById("p-rings");
  if (c.championships > 0) {
    ringsEl.textContent = "CHAMPIONSHIP COUNT: " + "🏆".repeat(c.championships);
    ringsEl.classList.remove("none");
  } else {
    ringsEl.textContent =
      "CHAMPIONSHIP COUNT: one can only dream of such glory";
    ringsEl.classList.add("none");
  }

  document.getElementById("p-record").textContent =
    `${c.wins}-${c.losses}-${c.ties}`;
  document.getElementById("p-playoff").textContent =
    `${manager.playoff_record.playoff_wins}-${manager.playoff_record.playoff_losses}`;
  document.getElementById("p-winpct").textContent =
    (c.win_pct * 100).toFixed(1) + "%";
  document.getElementById("p-avg").textContent = c.avg_points_per_match;
  document.getElementById("p-pf").textContent = c.points_for.toLocaleString();
  document.getElementById("p-pa").textContent =
    c.points_against.toLocaleString();
  document.getElementById("p-trades").textContent = c.trades;
  document.getElementById("p-years").textContent =
    `${c.years_played[0]}–${c.years_played[c.years_played.length - 1]}`;
  document.getElementById("p-lastplace").textContent = c.last_place_finishes;

  const finish = c.best_finish;
  const ordinal =
    finish === 1
      ? "1ST"
      : finish === 2
        ? "2ND"
        : finish === 3
          ? "3RD"
          : finish + "TH";
  document.getElementById("p-bestfinish").textContent = ordinal;
  document.getElementById("p-avgplacement").textContent = c.avg_final_placement;

  document.getElementById("p-drought").textContent =
    c.championship_drought === "never won"
      ? "NEVER WON"
      : `${c.championship_drought} SEASONS`;

  const rival = manager.rivalry_highlights.toughest_rival;
  const fav = manager.rivalry_highlights.favorite_opponent;
  const longest = manager.rivalry_highlights.longest_running_rivalry;

  document.getElementById("p-toughest").textContent = rival
    ? `${rival.opponent} (${rival.wins_over_them}-${rival.losses_to_them})`
    : "—";
  document.getElementById("p-favorite").textContent = fav
    ? `${fav.opponent} (${fav.wins_over_them}-${fav.losses_to_them})`
    : "—";
  document.getElementById("p-longest").textContent = longest
    ? `${longest.opponent} (${longest.total_games} games)`
    : "—";

  const profileEl = document.getElementById("profile");
  profileEl.classList.add("open");
  profileEl.scrollIntoView({ behavior: "smooth" });
}

function closeProfile() {
  document.getElementById("profile").classList.remove("open");
}

document.addEventListener("DOMContentLoaded", loadManagers);
