/*
  js/analytics-sim.js

  Fetches data/raw_analytics/championship_sim.json, renders:
    1. Horizontal bar chart, one bar per champion, length = simulated
       championship win probability, colored by luck_label.
    2. Champion cards, one per year, with a badge showing their label.
    3. Methodology section - ALSO summarized in a prominent intro box
       at the TOP of the page (before any numbers), since this page's
       results could easily be misread as an attack on a real
       championship rather than a measure of how close the games were.

  Color mapping deliberately avoids red for "MIRACLE RUN" - red reads
  as failure/wrong, but a miracle run isn't a bad thing, it's a fun,
  dramatic story. Pink is used instead, consistent with how pink marks
  other "special/highlight" things elsewhere on the site.
*/

const DATA_PATH = "data/raw_analytics/championship_sim.json";

const LABEL_COLORS = {
  DOMINANT: "#ffcc00",
  DESERVED: "#00ff88",
  "LUCKY RUN": "#2060e0",
  "MIRACLE RUN": "#ff0055",
};

const BADGE_CLASS = {
  DOMINANT: "gold",
  DESERVED: "green",
  "LUCKY RUN": "blue",
  "MIRACLE RUN": "pink",
};

let simData = null;

async function init() {
  const res = await fetch(DATA_PATH);
  if (!res.ok) {
    console.error("Failed to load championship_sim.json:", res.status);
    return;
  }
  simData = await res.json();

  renderChart();
  renderCards();
  renderMethodology();
}

function renderChart() {
  const sims = [...simData.simulations].sort((a, b) => a.year - b.year);

  new Chart(document.getElementById("sim-chart"), {
    type: "bar",
    data: {
      labels: sims.map((s) => `${s.year} - ${s.champion}`),
      datasets: [
        {
          label: "Simulated Championship Probability",
          data: sims.map((s) => s.simulated_championship_probability * 100),
          backgroundColor: sims.map(
            (s) => LABEL_COLORS[s.luck_label] || "#888",
          ),
        },
      ],
    },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) =>
              `${ctx.raw.toFixed(1)}% win probability across 10,000 simulated replays`,
          },
        },
      },
      scales: {
        x: {
          min: 0,
          max: 100,
          title: { display: true, text: "Win Probability (%)", color: "#888" },
          ticks: { color: "#888" },
          grid: { color: "#222" },
        },
        y: {
          ticks: { color: "#e8e8e8", font: { family: "monospace", size: 11 } },
          grid: { display: false },
        },
      },
    },
  });
}

function renderCards() {
  const sims = [...simData.simulations].sort((a, b) => b.year - a.year);
  const grid = document.getElementById("champion-grid");

  grid.innerHTML = sims
    .map(
      (s) => `
    <div class="champion-card">
      <div class="champion-year">${s.year}</div>
      <div class="champion-name">${s.champion}</div>
      <div class="champion-prob">${(s.simulated_championship_probability * 100).toFixed(1)}%</div>
      <span class="badge ${BADGE_CLASS[s.luck_label] || "dim"}">${s.luck_label}</span>
      <div class="champion-meta">${s.games_in_bracket_run} playoff game${s.games_in_bracket_run === 1 ? "" : "s"} in bracket run</div>
    </div>
  `,
    )
    .join("");
}

const FAQ_ITEMS = [
  {
    q: "How exactly is this number calculated?",
    a: "For each champion's ACTUAL playoff bracket (their real opponents, real byes, exact same path that really happened), we replay every game 10,000 times using both teams' REAL regular-season scoring average and variance to randomly generate a score for each side each time. We count how many of the 10,000 replays the real champion wins EVERY game in their path. That fraction is the probability shown.",
  },
  {
    q: "Does a low percentage mean the championship wasn't 'real' or deserved?",
    a: "No. It means the games in that specific bracket run were genuinely close - close enough that normal week-to-week variance could plausibly have flipped a result or two. The championship still happened, on the field, for real. This number describes how MUCH margin for error there was, not whether the outcome should be second-guessed.",
  },
  {
    q: "Why do different champions get such different percentages?",
    a: "It comes down to how close their specific games were. A champion who wins their bracket by 20+ points every round will show a high percentage, since that big a gap rarely flips even with realistic randomness. A champion who survives a string of 2-3 point nail-biters will show a lower percentage, since those margins genuinely could go either way on any given week - that's not a flaw, it's just a more dramatic run.",
  },
  {
    q: "What do the labels (DOMINANT / DESERVED / LUCKY RUN / MIRACLE RUN) mean?",
    a: "They're just a plain-language way to describe the probability range: DOMINANT (45%+) means they'd likely win that bracket most of the time. DESERVED (25-45%) means a real, solid favorite. LUCKY RUN (10-25%) means the margins were tight enough that it easily could have gone another way. MIRACLE RUN (under 10%) means a genuinely dramatic, could-have-gone-either-way path to the title - which is a great story, not a bad one.",
  },
  {
    q: "Why these specific percentages, and why aren't they recalculated automatically?",
    a: "These cutoffs are calibrated to THIS league's real observed range (across 8 champions so far, from about 3% to 53%) rather than arbitrary round numbers - the original thresholds meant \"DOMINANT\" had never once been reached, and 5 of 8 champions were all lumped into the single most dramatic label despite having meaningfully different probabilities. They're intentionally FIXED, not recalculated fresh each season, unlike some other stats on this site - with only one data point per year, dynamic thresholds would be too coarse, and would retroactively relabel past champions every time a new season is added, which isn't the goal here.",
  },
];

function renderMethodology() {
  const wrap = document.getElementById("faq-list");
  wrap.innerHTML = FAQ_ITEMS.map(
    (item, i) => `
    <div class="faq-item">
      <div class="faq-question" onclick="toggleFaq(${i})">
        <span>${item.q}</span>
        <span class="faq-arrow" id="faq-arrow-${i}">+</span>
      </div>
      <div class="faq-answer" id="faq-answer-${i}">${item.a}</div>
    </div>
  `,
  ).join("");
}

function toggleFaq(i) {
  const answer = document.getElementById(`faq-answer-${i}`);
  const arrow = document.getElementById(`faq-arrow-${i}`);
  const isOpen = answer.classList.toggle("open");
  arrow.textContent = isOpen ? "−" : "+";
}

document.addEventListener("DOMContentLoaded", init);
