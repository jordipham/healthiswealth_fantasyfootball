/*
  js/index.js

  Fetches hall_of_champions.json, rivalry_lanes.json, and
  manager_profiles.json to populate the homepage's screen ticker and
  the three data-driven teaser cards (Reigning Champion, Fiercest
  Rivalry, Championship Drought). The Weekly Survey, Weekly News
  Update, and Matchup of the Week cards are intentionally NOT wired
  to any data source - those are manually edited directly in
  index.html each week (see the HTML comment there).
*/

const HALL_PATH = "data/derived/hall_of_champions.json";
const RIVALRY_PATH = "data/derived/rivalry_lanes.json";
const PROFILES_PATH = "data/derived/manager_profiles.json";

async function init() {
  const [hallRes, rivalryRes, profilesRes] = await Promise.all([
    fetch(HALL_PATH),
    fetch(RIVALRY_PATH),
    fetch(PROFILES_PATH),
  ]);

  if (!hallRes.ok || !rivalryRes.ok || !profilesRes.ok) {
    console.error("Failed to load one or more homepage data sources");
    return;
  }

  const hallData = await hallRes.json();
  const rivalryData = await rivalryRes.json();
  const profilesData = await profilesRes.json();

  renderReigningChampion(hallData);
  renderFiercestRivalry(rivalryData);
  renderChampionshipDrought(profilesData);
  renderTicker(hallData, rivalryData, profilesData);
}

function renderReigningChampion(hallData) {
  const latest = hallData.reduce((a, b) => (b.year > a.year ? b : a));
  document.getElementById("champ-name").textContent = latest.owners_display;
  document.getElementById("champ-year").textContent = latest.year;
}

function renderFiercestRivalry(rivalryData) {
  const top = rivalryData.superlatives.most_lopsided_rivalries[0];
  if (!top) return;
  document.getElementById("rivalry-desc").textContent =
    `${top.manager_a} vs ${top.manager_b}`;
}

function renderChampionshipDrought(profilesData) {
  // Longest NUMERIC drought only - excludes managers who have never
  // won at all ("never won" isn't comparable to a season count, and
  // conflates two different stories: "hasn't repeated" vs "hasn't won yet").
  const withDrought = Object.values(profilesData)
    .filter(m => typeof m.career.championship_drought === "number");

  if (withDrought.length === 0) return;

  const longest = withDrought.reduce((a, b) =>
    b.career.championship_drought > a.career.championship_drought ? b : a
  );

  document.getElementById("drought-name").textContent = longest.owner_name;
  document.getElementById("drought-seasons").textContent =
    `${longest.career.championship_drought} SEASON${longest.career.championship_drought === 1 ? "" : "S"}`;
}

function renderTicker(hallData, rivalryData, profilesData) {
  const latest = hallData.reduce((a, b) => (b.year > a.year ? b : a));

  const withDrought = Object.values(profilesData)
    .filter(m => typeof m.career.championship_drought === "number");
  const longestDrought = withDrought.length
    ? withDrought.reduce((a, b) => b.career.championship_drought > a.career.championship_drought ? b : a)
    : null;

  const parts = [
    `REIGNING CHAMP: ${latest.owners_display.toUpperCase()} (${latest.year})`,
    longestDrought
      ? `LONGEST DROUGHT: ${longestDrought.career.championship_drought} SEASONS (${longestDrought.owner_name.toUpperCase()})`
      : null,
    `${rivalryData.matchups.length} RIVALRIES TRACKED`,
  ].filter(Boolean);

  document.getElementById("ticker-text").textContent = parts.join("     •     ") + "     •     ";
}

document.addEventListener("DOMContentLoaded", init);
