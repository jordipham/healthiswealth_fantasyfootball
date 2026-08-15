/*
  js/standings.js

  Fetches data/derived/standings_archive.json and renders a year
  selector strip plus a sortable results table for the selected year.

  Field names below match standings_archive.json exactly as produced
  by compute_standings_archive.py.
*/

const DATA_PATH = "data/derived/standings_archive.json";

let standingsData = null;
let currentYear = null;
let sortState = { key: "final_standing", asc: true };

async function init() {
  const res = await fetch(DATA_PATH);
  if (!res.ok) {
    console.error("Failed to load standings_archive.json:", res.status);
    return;
  }
  standingsData = await res.json();

  const years = Object.keys(standingsData).sort((a, b) => Number(a) - Number(b));
  renderYearStrip(years);

  // Default to the most recent year
  selectYear(years[years.length - 1]);
}

function renderYearStrip(years) {
  const strip = document.getElementById("year-strip");
  years.forEach(year => {
    const tab = document.createElement("div");
    tab.className = "year-tab";
    tab.textContent = year;
    tab.dataset.year = year;
    tab.onclick = () => selectYear(year);
    strip.appendChild(tab);
  });
}

function selectYear(year) {
  currentYear = year;
  sortState = { key: "final_standing", asc: true }; // reset sort each time a new year is picked

  document.querySelectorAll(".year-tab").forEach(t => {
    t.classList.toggle("active", t.dataset.year === year);
  });

  const yearData = standingsData[year];
  document.getElementById("results-title").textContent =
    `— ${year} SEASON — ${yearData.league_size} MANAGERS —`;

  renderRows();
}

function renderRows() {
  const yearData = standingsData[currentYear];
  const rows = [...yearData.standings];

  rows.sort((a, b) => {
    let av = a[sortState.key];
    let bv = b[sortState.key];
    if (typeof av === "string") { av = av.toLowerCase(); bv = bv.toLowerCase(); }
    if (av < bv) return sortState.asc ? -1 : 1;
    if (av > bv) return sortState.asc ? 1 : -1;
    return 0;
  });

  const container = document.getElementById("rows");
  container.innerHTML = "";

  rows.forEach(r => {
    const div = document.createElement("div");
    div.className = "row" + (r.is_champion ? " champ" : "");

    const rankLabel = ordinal(r.final_standing);
    const champTag = r.is_champion ? `<span class="champ-tag">🏆</span>` : "";

    div.innerHTML = `
      <span class="place">${rankLabel}</span>
      <span class="name">${r.owners_display}${champTag}</span>
      <span class="team">${r.team_name}</span>
      <span class="record">${r.record}</span>
      <span class="pf">${r.points_for.toFixed(1)}</span>
      <span class="pa">${r.points_against.toFixed(1)}</span>
    `;
    container.appendChild(div);
  });

  updateSortArrow();
}

function ordinal(n) {
  if (n === 1) return "1ST";
  if (n === 2) return "2ND";
  if (n === 3) return "3RD";
  return `${n}TH`;
}

function sortBy(key) {
  if (sortState.key === key) {
    sortState.asc = !sortState.asc;
  } else {
    sortState = { key, asc: true };
  }
  renderRows();
}

function updateSortArrow() {
  document.querySelectorAll(".sort-arrow").forEach(el => el.textContent = "");
  const map = {
    final_standing: "arrow-place",
    owners_display: "arrow-name",
    team_name: "arrow-team",
    points_for: "arrow-pf",
    points_against: "arrow-pa",
  };
  const arrowId = map[sortState.key];
  if (arrowId) {
    document.getElementById(arrowId).textContent = sortState.asc ? "▲" : "▼";
  }
}

document.addEventListener("DOMContentLoaded", init);
