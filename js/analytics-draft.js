/*
  js/analytics-draft.js

  Fetches data/raw_analytics/draft_accuracy.json, renders:
    1. Scatter chart: ALL team-seasons pooled (~94 points) - total
       drafted-roster projected points (X) vs actual final standing
       (Y, axis REVERSED so "up" visually means a better finish,
       matching normal intuition).
    2. Bar chart: per-season Spearman correlation, one bar per year -
       visualizes the real swing this league shows (strong positive
       some years, negative others).
    3. Year selector + table, same pattern as standings.js, showing
       that season's team-by-team breakdown.
    4. Methodology section.
*/

const DATA_PATH = "data/raw_analytics/draft_accuracy.json";

const COLORS = {
  gold: "#ffcc00",
  green: "#00ff88",
  pink: "#ff0055",
  blue: "#2060e0",
  red: "#e02020",
  textDim: "#888888",
};

let draftAccuracyData = null;
let currentYear = null;

async function init() {
  const res = await fetch(DATA_PATH);
  if (!res.ok) {
    console.error("Failed to load draft_accuracy.json:", res.status);
    return;
  }
  draftAccuracyData = await res.json();

  renderSummary();
  renderPooledScatter();
  renderYearlyCorrelationChart();
  renderYearStrip();
  renderMethodology();

  const years = Object.keys(draftAccuracyData.seasons).sort((a, b) => Number(b) - Number(a));
  selectYear(years[0]);
}

function renderSummary() {
  document.getElementById("summary-overall").textContent = draftAccuracyData.overall.spearman_correlation;
  document.getElementById("summary-teamseasons").textContent = draftAccuracyData.overall.total_team_seasons;

  const seasons = draftAccuracyData.seasons;
  let best = null, worst = null;
  for (const [year, s] of Object.entries(seasons)) {
    if (s.spearman_correlation === null) continue;
    if (best === null || s.spearman_correlation > seasons[best].spearman_correlation) best = year;
    if (worst === null || s.spearman_correlation < seasons[worst].spearman_correlation) worst = year;
  }
  document.getElementById("summary-best-year").textContent = `${best} (${seasons[best].spearman_correlation})`;
  document.getElementById("summary-worst-year").textContent = `${worst} (${seasons[worst].spearman_correlation})`;
}

function renderPooledScatter() {
  const allTeams = [];
  Object.entries(draftAccuracyData.seasons).forEach(([year, s]) => {
    s.teams.forEach(t => allTeams.push({ ...t, year }));
  });

  const points = allTeams.map(t => ({
    x: t.total_projected_points,
    y: t.final_standing,
    label: `${t.owner_name} (${t.year})`,
  }));

  new Chart(document.getElementById("pooled-scatter"), {
    type: "scatter",
    data: {
      datasets: [{
        label: "Team-Seasons",
        data: points,
        backgroundColor: COLORS.blue,
        pointRadius: 5,
        pointHoverRadius: 7,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const p = points[ctx.dataIndex];
              return `${p.label}: ${p.x.toFixed(0)} projected pts, finished ${p.y}`;
            },
          },
        },
      },
      scales: {
        x: {
          title: { display: true, text: "Total Projected Points (Drafted Players)", color: COLORS.textDim },
          ticks: { color: COLORS.textDim },
          grid: { color: "#222" },
        },
        y: {
          reverse: true,
          title: { display: true, text: "Final Standing (lower = better)", color: COLORS.textDim },
          ticks: { color: COLORS.textDim, stepSize: 1 },
          grid: { color: "#222" },
        },
      },
    },
  });
}

function renderYearlyCorrelationChart() {
  const years = Object.keys(draftAccuracyData.seasons).sort((a, b) => Number(a) - Number(b));
  const correlations = years.map(y => draftAccuracyData.seasons[y].spearman_correlation);

  new Chart(document.getElementById("yearly-correlation-chart"), {
    type: "bar",
    data: {
      labels: years,
      datasets: [{
        label: "Spearman Correlation (projected points rank vs actual finish rank)",
        data: correlations,
        backgroundColor: correlations.map(c => c >= 0 ? COLORS.green : COLORS.red),
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
          ticks: { color: COLORS.textDim },
          grid: { display: false },
        },
        y: {
          min: -1,
          max: 1,
          ticks: { color: COLORS.textDim },
          grid: { color: "#222" },
        },
      },
    },
  });
}

function renderYearStrip() {
  const years = Object.keys(draftAccuracyData.seasons).sort((a, b) => Number(a) - Number(b));
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
  document.querySelectorAll(".year-tab").forEach(t => {
    t.classList.toggle("active", t.dataset.year === year);
  });

  const season = draftAccuracyData.seasons[year];
  document.getElementById("year-correlation-label").textContent =
    `${year} SEASON — CORRELATION: ${season.spearman_correlation}`;

  const rows = [...season.teams].sort((a, b) => a.final_standing - b.final_standing);
  const tbody = document.getElementById("table-body");
  tbody.innerHTML = rows.map(t => `
    <tr>
      <td>${t.final_standing}</td>
      <td>${t.owner_name}</td>
      <td>${t.total_projected_points}</td>
      <td>${t.picks_with_known_projection}/${t.total_picks}</td>
    </tr>
  `).join("");
}

const FAQ_ITEMS = [
  {
    q: "What exactly is being summed for 'total projected points'?",
    a: "Only players a team actually DRAFTED that year - not their full end-of-season roster. A team's final roster includes players added later via trades and waivers, which would mix in-season roster management skill with draft-day evaluation. This analysis is scoped specifically to how good the DRAFT looked on paper, before any of those later moves happened."
  },
  {
    q: "What is Spearman correlation, in plain terms?",
    a: "It measures whether two RANKINGS move together - not the raw numbers, just the order. A value near +1.0 means 'the team with the best projected roster tends to finish highest, the second-best projected tends to finish second-highest,' and so on down the list. A value near 0 means projected strength and actual finish have little relationship. A negative value would mean the opposite - higher projections tending to predict WORSE finishes."
  },
  {
    q: "Why is the overall correlation only 0.20 - doesn't that mean projections are useless?",
    a: "Weak-but-positive is actually a realistic, honest result - it means preseason evaluations have SOME real predictive signal, but a huge amount of what determines a season (in-season trades, injuries, waiver-wire luck, close-game variance) isn't captured by draft day alone. The per-season breakdown makes this more visible - some years show a strong relationship, others show almost none, which is exactly what you'd expect if skill and randomness are both real factors."
  },
  {
    q: "Why do some teams show 'picks_with_known_projection' lower than their total picks?",
    a: "Some drafted players were dropped and never picked up by anyone else all season - for those players, no point total OR projection is recoverable in this data (a known limitation shared with the Draft Day Recaps page). This means a team's total projected points can be a slight undercount if several of their picks vanished entirely, which is shown transparently here rather than hidden."
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
