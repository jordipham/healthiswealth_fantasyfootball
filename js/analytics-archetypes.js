/*
  js/analytics-archetypes.js

  Fetches data/raw_analytics/manager_archetypes.json, renders:
    1. Scatter chart: retention_rate (X) vs trades_per_season (Y),
       colored by cluster - these two features separate clusters most
       visibly of the 4 used.
    2. Cluster cards, one per archetype, listing members + centroid
       stats in real units.
    3. Small-sample caveat, shown prominently, not buried.
    4. Methodology section.
*/

const DATA_PATH = "data/raw_analytics/manager_archetypes.json";

const CLUSTER_COLORS = ["#ffcc00", "#00ff88", "#ff0055", "#2060e0"];

let archetypeData = null;

async function init() {
  const res = await fetch(DATA_PATH);
  if (!res.ok) {
    console.error("Failed to load manager_archetypes.json:", res.status);
    return;
  }
  archetypeData = await res.json();

  renderScatter();
  renderClusterCards();
  renderMethodology();
}

function renderScatter() {
  const managers = Object.values(archetypeData.managers);

  const datasets = archetypeData.clusters.map((cluster, i) => ({
    label: cluster.archetype,
    data: managers
      .filter(m => m.cluster_id === cluster.cluster_id)
      .map(m => ({
        x: m.features.retention_rate,
        y: m.features.trades_per_season,
        label: m.owner_name,
      })),
    backgroundColor: CLUSTER_COLORS[i % CLUSTER_COLORS.length],
    pointRadius: 7,
    pointHoverRadius: 9,
  }));

  new Chart(document.getElementById("archetype-scatter"), {
    type: "scatter",
    data: { datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: "#e8e8e8", font: { family: "monospace", size: 11 } } },
        tooltip: {
          callbacks: {
            label: (ctx) => `${ctx.raw.label}: ${(ctx.raw.x * 100).toFixed(0)}% retention, ${ctx.raw.y.toFixed(1)} trades/season`,
          },
        },
      },
      scales: {
        x: {
          title: { display: true, text: "Retention Rate", color: "#888" },
          ticks: { color: "#888" },
          grid: { color: "#222" },
        },
        y: {
          title: { display: true, text: "Trades Per Season", color: "#888" },
          ticks: { color: "#888" },
          grid: { color: "#222" },
        },
      },
    },
  });
}

function renderClusterCards() {
  const grid = document.getElementById("cluster-grid");
  grid.innerHTML = archetypeData.clusters.map((c, i) => `
    <div class="cluster-card" style="border-color: ${CLUSTER_COLORS[i % CLUSTER_COLORS.length]};">
      <div class="cluster-archetype" style="color: ${CLUSTER_COLORS[i % CLUSTER_COLORS.length]};">${c.archetype}</div>
      <div class="cluster-count">${c.member_count} MANAGERS</div>
      <div class="cluster-members">${c.members.join(", ")}</div>
      <div class="cluster-centroid">
        WIN %: ${(c.centroid_real_units.win_pct * 100).toFixed(1)}%<br>
        RETENTION: ${(c.centroid_real_units.retention_rate * 100).toFixed(1)}%<br>
        TRADES/SEASON: ${c.centroid_real_units.trades_per_season.toFixed(2)}<br>
        SCORE VOLATILITY (CV): ${c.centroid_real_units.coefficient_of_variation.toFixed(4)}
      </div>
    </div>
  `).join("");
}

const FAQ_ITEMS = [
  {
    q: "How were these groups actually formed?",
    a: "Using k-means clustering, a standard unsupervised machine learning method - it groups managers into clusters based on similarity across 4 features (career win %, draft retention rate, trades per season, and scoring volatility), without being told in advance what the groups 'should' look like. Each feature is standardized first, so no single feature dominates the grouping just because it happens to have a larger numeric range."
  },
  {
    q: "How are the archetype names (like 'Wheeler-Dealer') chosen?",
    a: "Automatically, from whichever feature that cluster's average member deviates from most compared to the overall league average - not a fixed, hand-picked list. If the underlying data shifts in future seasons, the labels can shift with it, rather than staying locked to categories that no longer fit."
  },
  {
    q: "Why only 4 features - couldn't more data make this more accurate?",
    a: "With only 15 managers total, adding more features actually makes clustering LESS reliable, not more - a small dataset spread across too many dimensions becomes sparse and the groupings stop being meaningful. 4 was a deliberate choice to keep this interpretable at this sample size."
  },
  {
    q: "Should I take my cluster assignment very seriously?",
    a: "Treat it as a fun, honest snapshot, not a rigorous personality profile. With only 15 data points, clustering results CAN shift meaningfully if even one or two managers' stats change significantly, or as more managers/seasons get added over time. This is explicitly illustrative, not a statistically robust classification."
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
