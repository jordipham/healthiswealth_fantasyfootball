/*
  js/analytics-rivalry.js

  Fetches data/raw_analytics/rivalry_analytics.json, renders:
    1. Bar chart: total_games_all_rivalries per manager, ranked -
       ranks who has the deepest cumulative head-to-head history.
    2. Cards for the statistically significant rivalries specifically.
    3. Full sortable significance table for all 105 rivalries.
    4. A note explaining why no network graph/centrality visual exists
       here - the rivalry graph is a COMPLETE graph (all 105 possible
       pairs connected), which makes those measures structurally
       meaningless, not just uncomputed.
*/

const DATA_PATH = "data/raw_analytics/rivalry_analytics.json";
const COLORS = { blue: "#2060e0", green: "#00ff88", textDim: "#888888" };

let rivalryAnalyticsData = null;
let sortState = { key: "p_value", asc: true };
let showSignificantOnly = false;

async function init() {
  const res = await fetch(DATA_PATH);
  if (!res.ok) {
    console.error("Failed to load rivalry_analytics.json:", res.status);
    return;
  }
  rivalryAnalyticsData = await res.json();

  renderVolumeChart();
  renderSignificantCards();
  renderTable();
  renderMethodology();
}

function renderVolumeChart() {
  const nodes = [...rivalryAnalyticsData.network.nodes].sort((a, b) => b.total_games_all_rivalries - a.total_games_all_rivalries);

  new Chart(document.getElementById("volume-chart"), {
    type: "bar",
    data: {
      labels: nodes.map(n => n.manager),
      datasets: [{
        label: "Total Games Across All Rivalries",
        data: nodes.map(n => n.total_games_all_rivalries),
        backgroundColor: COLORS.blue,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: "#e8e8e8", font: { family: "monospace" } } },
      },
      scales: {
        x: {
          ticks: { color: COLORS.textDim, font: { size: 9 } },
          grid: { display: false },
        },
        y: {
          ticks: { color: COLORS.textDim },
          grid: { color: "#222" },
        },
      },
    },
  });
}

function renderSignificantCards() {
  const significant = rivalryAnalyticsData.significance.filter(s => s.significant);
  const grid = document.getElementById("significant-grid");

  document.getElementById("significant-count").textContent = significant.length;

  grid.innerHTML = significant.map(s => `
    <div class="significant-card">
      <div class="significant-matchup">${s.manager_a} vs ${s.manager_b}</div>
      <div class="significant-record">${s.wins_a} - ${s.wins_b}</div>
      <div class="significant-pvalue">p = ${s.p_value} (${s.games_played} games)</div>
    </div>
  `).join("");
}

function renderTable() {
  let rows = [...rivalryAnalyticsData.significance];
  if (showSignificantOnly) {
    rows = rows.filter(r => r.significant);
  }

  rows.sort((a, b) => {
    let av = a[sortState.key];
    let bv = b[sortState.key];
    if (av === null) av = sortState.key === "p_value" ? 999 : av;
    if (bv === null) bv = sortState.key === "p_value" ? 999 : bv;
    if (typeof av === "string") { av = av.toLowerCase(); bv = bv.toLowerCase(); }
    if (av < bv) return sortState.asc ? -1 : 1;
    if (av > bv) return sortState.asc ? 1 : -1;
    return 0;
  });

  const tbody = document.getElementById("table-body");
  tbody.innerHTML = rows.map(r => `
    <tr>
      <td>${r.manager_a}</td>
      <td>${r.manager_b}</td>
      <td>${r.games_played}</td>
      <td>${r.wins_a != null ? r.wins_a + "-" + r.wins_b : "—"}</td>
      <td>${r.p_value != null ? r.p_value : "N/A"}</td>
      <td>${r.significant ? '<span class="badge gold">SIGNIFICANT</span>' : "—"}</td>
    </tr>
  `).join("");
}

function sortTable(key) {
  if (sortState.key === key) {
    sortState.asc = !sortState.asc;
  } else {
    sortState = { key, asc: true };
  }
  renderTable();
}

function toggleSignificantFilter() {
  showSignificantOnly = document.getElementById("significant-filter").checked;
  renderTable();
}

const FAQ_ITEMS = [
  {
    q: "Why is there no rivalry network graph or 'who's most central' visual?",
    a: "This league's rivalry graph is a COMPLETE graph - all 105 of 105 possible manager pairs have played each other. Graph centrality measures (like betweenness centrality) identify who 'bridges' the shortest connection between other pairs - but in a complete graph, every pair already has a direct connection, so there's never a structural reason to route through a third person. That measurement is genuinely meaningless here, not just uncomputed. The one real signal left is total cumulative games across all rivalries, which IS shown above."
  },
  {
    q: "What does the p-value actually mean here?",
    a: "It's the probability of seeing a win/loss split at least this lopsided by pure random chance, if the true underlying odds were a 50/50 coin flip. A LOW p-value (under 0.05) means the record is unlikely to be random noise. Ties are excluded from this calculation - only decisive games count."
  },
  {
    q: "A rivalry looks really lopsided (like 0-5) but isn't flagged as significant - why?",
    a: "With very few games, even a perfect sweep can still be statistically consistent with random chance. A 5-0 record has a two-sided p-value of 0.0625 - just above the conventional 0.05 significance threshold - meaning even a perfect sweep in only 5 games isn't quite enough games to rule out coincidence. It's still a real, lopsided record - it's just not (yet) enough games to say it's definitely not luck."
  },
  {
    q: "Rivalries with fewer than 3 games show 'sample too small' - why not just compute it anyway?",
    a: "A p-value from 1-2 games would be almost meaningless and could be actively misleading if presented alongside real statistics from rivalries with dozens of games. Rather than show a number that looks precise but isn't meaningful, those are flagged honestly instead."
  },
];

function renderMethodology() {
  const wrap = document.getElementById("faq-list");
  wrap.innerHTML = FAQ_ITEMS.map((item, i) => `
    <div class="faq-item">
      <div class="faq-question" onclick="toggleFaq(${i})">
        <span>${item.q}</span>
        <span class="faq-arrow" id="faq-arrow-${i}">+</span>
      </div>
      <div class="faq-answer" id="faq-answer-${i}">${item.a}</div>
    </div>
  `).join("");
}

function toggleFaq(i) {
  const answer = document.getElementById(`faq-answer-${i}`);
  const arrow = document.getElementById(`faq-arrow-${i}`);
  const isOpen = answer.classList.toggle("open");
  arrow.textContent = isOpen ? "−" : "+";
}

document.addEventListener("DOMContentLoaded", init);
