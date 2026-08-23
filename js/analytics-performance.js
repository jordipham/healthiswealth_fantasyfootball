/*
  js/analytics-performance.js

  Fetches data/raw_analytics/performance_patterns.json, renders:
    1. Scatter chart: actual wins vs expected wins (career level, one
       point per manager) with a reference line for "exactly as
       expected" - points above the line got MORE wins than their
       scoring predicts (favorable luck), below = the opposite.
    2. Bar chart: coefficient of variation per manager (scoring
       consistency/volatility), sorted.
    3. Full data table, sortable, career-level breakdown per manager.
    4. Methodology section explaining the math BEFORE anyone reacts
       to their own number.

  Uses Chart.js (loaded via CDN in the HTML <head>) - the first page
  on this site to use an external charting library. Colors are
  hardcoded to match css/style.css's CSS variables, since Chart.js
  config can't read CSS custom properties directly.
*/

const DATA_PATH = "data/raw_analytics/performance_patterns.json";

const COLORS = {
  gold: "#ffcc00",
  green: "#00ff88",
  pink: "#ff0055",
  blue: "#2060e0",
  red: "#e02020",
  textDim: "#888888",
  bgPanel: "#1a1a2e",
};

let performanceData = null;
let sortState = { key: "luck_differential", asc: false };

async function init() {
  const res = await fetch(DATA_PATH);
  if (!res.ok) {
    console.error("Failed to load performance_patterns.json:", res.status);
    return;
  }
  performanceData = await res.json();

  renderSummary();
  renderLuckChart();
  renderConsistencyChart();
  renderTable();
  renderMethodology();
}

function renderSummary() {
  const career = Object.values(performanceData.career);
  const mostLucky = career.reduce((a, b) => b.luck_differential > a.luck_differential ? b : a);
  const mostUnlucky = career.reduce((a, b) => b.luck_differential < a.luck_differential ? b : a);
  const mostConsistent = career.reduce((a, b) =>
    (b.coefficient_of_variation ?? Infinity) < (a.coefficient_of_variation ?? Infinity) ? b : a
  );

  document.getElementById("summary-lucky").textContent = `${mostLucky.owner_name} (+${mostLucky.luck_differential})`;
  document.getElementById("summary-unlucky").textContent = `${mostUnlucky.owner_name} (${mostUnlucky.luck_differential})`;
  document.getElementById("summary-consistent").textContent = mostConsistent.owner_name;
}

function renderLuckChart() {
  const career = performanceData.career;
  const points = Object.values(career).map(m => ({
    x: m.expected_wins,
    y: m.actual_wins,
    label: m.owner_name,
  }));

  const minVal = Math.min(...points.map(p => Math.min(p.x, p.y))) - 5;
  const maxVal = Math.max(...points.map(p => Math.max(p.x, p.y))) + 5;

  new Chart(document.getElementById("luck-chart"), {
    type: "scatter",
    data: {
      datasets: [
        {
          label: "Managers",
          data: points,
          backgroundColor: COLORS.green,
          pointRadius: 6,
          pointHoverRadius: 8,
        },
        {
          label: "Expected = Actual (no luck)",
          data: [{ x: minVal, y: minVal }, { x: maxVal, y: maxVal }],
          type: "line",
          borderColor: COLORS.textDim,
          borderDash: [6, 4],
          pointRadius: 0,
          fill: false,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: "#e8e8e8", font: { family: "monospace" } } },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              if (ctx.dataset.label === "Managers") {
                const p = points[ctx.dataIndex];
                return `${p.label}: ${p.y} actual / ${p.x} expected wins`;
              }
              return null;
            },
          },
        },
      },
      scales: {
        x: {
          title: { display: true, text: "Expected Wins", color: COLORS.textDim },
          ticks: { color: COLORS.textDim },
          grid: { color: "#222" },
        },
        y: {
          title: { display: true, text: "Actual Wins", color: COLORS.textDim },
          ticks: { color: COLORS.textDim },
          grid: { color: "#222" },
        },
      },
    },
  });
}

function renderConsistencyChart() {
  const career = Object.values(performanceData.career)
    .filter(m => m.coefficient_of_variation != null)
    .sort((a, b) => a.coefficient_of_variation - b.coefficient_of_variation);

  new Chart(document.getElementById("consistency-chart"), {
    type: "bar",
    data: {
      labels: career.map(m => m.owner_name),
      datasets: [{
        label: "Coefficient of Variation (lower = more consistent)",
        data: career.map(m => m.coefficient_of_variation),
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

function renderTable() {
  const rows = Object.values(performanceData.career);

  rows.sort((a, b) => {
    let av = a[sortState.key];
    let bv = b[sortState.key];
    if (typeof av === "string") { av = av.toLowerCase(); bv = bv.toLowerCase(); }
    if (av < bv) return sortState.asc ? -1 : 1;
    if (av > bv) return sortState.asc ? 1 : -1;
    return 0;
  });

  const tbody = document.getElementById("table-body");
  tbody.innerHTML = rows.map(m => `
    <tr>
      <td>${m.owner_name}</td>
      <td>${m.actual_wins}</td>
      <td>${m.expected_wins}</td>
      <td class="${m.luck_differential > 0 ? "positive" : m.luck_differential < 0 ? "negative" : ""}">${m.luck_differential > 0 ? "+" : ""}${m.luck_differential}</td>
      <td>${m.score_stdev ?? "—"}</td>
      <td>${m.coefficient_of_variation ?? "—"}</td>
    </tr>
  `).join("");
}

function sortTable(key) {
  if (sortState.key === key) {
    sortState.asc = !sortState.asc;
  } else {
    sortState = { key, asc: false };
  }
  renderTable();
}

const FAQ_ITEMS = [
  {
    q: "What does 'expected wins' actually mean?",
    a: "For every REGULAR SEASON week, we rank a manager's score against every OTHER team's score that same week - not just their real opponent. Their expected win fraction that week = the fraction of opponents they would have beaten had they faced them instead. Summed across the season, this gives a manager's expected win total - what their record 'should' look like based purely on how many points they scored, independent of who they actually happened to play."
  },
  {
    q: "Why does the analysis stop at the regular season - what about playoffs?",
    a: "Playoffs are single-elimination brackets, not a full round-robin against the whole league - not everyone plays the same number of playoff games, and the comparison this method relies on (ranking against the WHOLE league each week) doesn't have the same meaning once the format changes. Both Luck vs. Skill and Consistency are scoped to regular season weeks only, for a fair, consistent comparison."
  },
  {
    q: "What does 'luck differential' mean, and is a negative number bad?",
    a: "luck_differential = actual_wins minus expected_wins. Positive means a manager won MORE than their scoring output alone predicts (a favorable schedule, or close wins going their way). Negative means the opposite - they scored well but still lost more often than expected, often from tough head-to-head luck. Neither is a judgment of skill - it's purely about how the schedule and matchup timing played out."
  },
  {
    q: "What is 'coefficient of variation' and why not just use standard deviation?",
    a: "Coefficient of variation = standard deviation divided by average score. Raw standard deviation alone isn't comparable across different seasons or eras where average scoring levels differ (e.g. if league-wide scoring trends up or down over the years) - dividing by the mean makes volatility genuinely comparable across any two managers or seasons, regardless of the underlying scoring level."
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
