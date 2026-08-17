// JAVASCRIPT FOR DRAFT DAY PAGE

/*
  js/draft-day.js

  Fetches data/derived/draft_day_profiler.json and manager_profiles.json.

  ERA SPLIT: each manager's card shows a Snake/Auction toggle IF they
  have picks in both eras. If they only have one era (real cases in
  this league: Jordi Pham is auction-only), NO toggle renders - just
  that single era's content under a static label.

  RARITY: both eras use the SAME four tier names (Legendary/Rare/
  Common/Junk) but computed from DIFFERENT underlying metrics -
  value_score for snake, points_per_dollar for auction. Thresholds
  are read directly from the JSON (computed dynamically in Python
  each run), never hardcoded here - this is a deliberate fix for a
  real bug we hit before, where hardcoded JS thresholds went stale
  after the QB exclusion changed the snake distribution.
*/

const DRAFT_DATA_PATH = "data/derived/draft_day_profiler.json";
const PROFILES_DATA_PATH = "data/derived/manager_profiles.json";
const PHOTO_PATH = (canonicalId) => `images/draft_day/${canonicalId}.jpg`;

let draftData = null;
let managerProfiles = null;
let rarityThresholds = null;

const RARITY_TAG = {
  legendary: "★ LEGENDARY",
  rare: "◆ RARE",
  common: "● COMMON",
  junk: "✕ JUNK",
};

function getRarity(value, era) {
  const t = rarityThresholds[era];
  if (!t || value === null || value === undefined) return "common";
  if (value < t.junk) return "junk";
  if (value < t.common) return "common";
  if (value < t.rare) return "rare";
  return "legendary";
}

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
  const [draftRes, profilesRes] = await Promise.all([
    fetch(DRAFT_DATA_PATH),
    fetch(PROFILES_DATA_PATH),
  ]);

  if (!draftRes.ok || !profilesRes.ok) {
    console.error("Failed to load draft or manager data");
    return;
  }

  draftData = await draftRes.json();
  managerProfiles = await profilesRes.json();
  rarityThresholds = draftData.notes.rarity_thresholds;

  renderGrid();
  renderFaq();
}

function renderGrid() {
  const grid = document.getElementById("grid");

  Object.entries(managerProfiles).forEach(([canonicalId, m]) => {
    const draftProfile = draftData.manager_profiles[canonicalId];
    if (!draftProfile) return;

    const card = document.createElement("div");
    card.className = "card" + (m.status === "retired" ? " retired" : "");
    card.onclick = () => {
      document
        .querySelectorAll(".card")
        .forEach((c) => c.classList.remove("active-pick"));
      card.classList.add("active-pick");
      showInventory(canonicalId, m, draftProfile);
    };

    card.innerHTML = `
      ${renderAvatar(canonicalId, "avatar-placeholder")}
      <div class="card-name">${m.owner_name.toUpperCase()}</div>
      <div class="card-status">${m.status.toUpperCase()}</div>
    `;
    grid.appendChild(card);
  });
}

/* ============ ITEM CARD RENDERERS ============ */

function buildItemCard(pick, era) {
  const rarity = getRarity(
    era === "snake" ? pick.value_score : pick.points_per_dollar,
    era,
  );
  const movedNote = pick.was_kept_by_drafter
    ? ""
    : `<div class="item-moved">MOVED TO: ${(pick.ended_with || []).join(" & ") || "UNKNOWN"}</div>`;

  const priceLine =
    era === "snake"
      ? `Round ${pick.round_num}, Pick ${pick.round_pick} &middot; ${pick.year}`
      : `$${pick.bid_amount} bid &middot; ${pick.year}`;

  return `
    <div class="item ${rarity}">
      <div class="rarity-tag">${RARITY_TAG[rarity]}</div>
      <div class="item-name">${pick.player_name}</div>
      <div class="item-meta">${priceLine}</div>
      <div class="item-points">${pick.total_points.toFixed(2)} PTS</div>
      ${movedNote}
    </div>
  `;
}

function buildStarItemCard(pick, era) {
  const movedNote = pick.was_kept_by_drafter
    ? ""
    : `<div class="item-moved">MOVED TO: ${(pick.ended_with || []).join(" & ") || "UNKNOWN"}</div>`;
  const priceLine =
    era === "snake"
      ? `Round ${pick.round_num}, Pick ${pick.round_pick} &middot; ${pick.year}`
      : `$${pick.bid_amount} bid &middot; ${pick.year}`;
  const tag = era === "snake" ? "⭐ EARLY-ROUND TARGET" : "⭐ BIG-MONEY SPENT";

  return `
    <div class="item star-item">
      <div class="rarity-tag">${tag}</div>
      <div class="item-name">${pick.player_name}</div>
      <div class="item-meta">${priceLine}</div>
      <div class="item-points">${pick.total_points.toFixed(2)} PTS</div>
      ${movedNote}
    </div>
  `;
}

function buildQbItemCard(pick) {
  const movedNote = pick.was_kept_by_drafter
    ? ""
    : `<div class="item-moved">MOVED TO: ${(pick.ended_with || []).join(" & ") || "UNKNOWN"}</div>`;
  const priceLine =
    pick.draft_type === "snake"
      ? `Round ${pick.round_num}, Pick ${pick.round_pick} &middot; ${pick.year}`
      : `$${pick.bid_amount} bid &middot; ${pick.year}`;

  return `
    <div class="item qb-item">
      <div class="rarity-tag">⚡ QB SEASON</div>
      <div class="item-name">${pick.player_name}</div>
      <div class="item-meta">${priceLine}</div>
      <div class="item-points">${pick.total_points.toFixed(2)} PTS</div>
      ${movedNote}
    </div>
  `;
}

/* ============ ERA SECTION RENDERING ============ */

function renderEraSection(eraKey, eraData) {
  const sections = [
    {
      id: `${eraKey}-best-value-list`,
      data: eraData.best_value_picks,
      empty: "No complete-data picks available.",
      renderer: (p) => buildItemCard(p, eraKey),
    },
    {
      id: `${eraKey}-stars-list`,
      data: eraData.stars,
      empty:
        eraKey === "snake"
          ? "No early-round hits found (round 1-4)."
          : "No expensive-bid hits found.",
      renderer: (p) => buildStarItemCard(p, eraKey),
    },
    {
      id: `${eraKey}-best-steals-list`,
      data: eraData.best_steals,
      empty:
        eraKey === "snake"
          ? "No late-round steals found (round 8+)."
          : "No cheap-bid steals found.",
      renderer: (p) => buildItemCard(p, eraKey),
    },
    {
      id: `${eraKey}-biggest-busts-list`,
      data: eraData.biggest_busts,
      empty:
        eraKey === "snake"
          ? "No early-round busts found (round 1-4)."
          : "No expensive-bid busts found.",
      renderer: (p) => buildItemCard(p, eraKey),
    },
  ];

  sections.forEach(({ id, data, empty, renderer }) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.innerHTML =
      data && data.length
        ? data.map(renderer).join("")
        : `<p class="item-meta">${empty}</p>`;
  });
}

function showInventory(canonicalId, managerMeta, draftProfile) {
  document.getElementById("inv-name").textContent =
    `${managerMeta.owner_name.toUpperCase()} — DRAFT LOG`;
  document.getElementById("inv-retention").textContent =
    `RETENTION RATE: ${(draftProfile.retention_rate * 100).toFixed(1)}% (${draftProfile.picks_kept}/${draftProfile.total_picks - draftProfile.picks_with_incomplete_data} PICKS KEPT)`;
  document.getElementById("inv-incomplete").textContent =
    draftProfile.picks_with_incomplete_data > 0
      ? `${draftProfile.picks_with_incomplete_data} PICKS HAVE NO RECOVERABLE OUTCOME (DROPPED & NEVER RECLAIMED BY ANYONE) — SEE FAQ`
      : "";

  // ===== ERA TOGGLE / FALLBACK LOGIC =====
  const toggleWrap = document.getElementById("era-toggle-wrap");
  const snakeBlock = document.getElementById("era-block-snake");
  const auctionBlock = document.getElementById("era-block-auction");

  const hasBoth = draftProfile.has_snake_era && draftProfile.has_auction_era;

  if (hasBoth) {
    toggleWrap.style.display = "flex";
    toggleWrap.innerHTML = `
      <div class="era-tab" id="era-tab-snake" onclick="switchEra('snake')">SNAKE DRAFT</div>
      <div class="era-tab" id="era-tab-auction" onclick="switchEra('auction')">AUCTION DRAFT</div>
    `;
    // Explicitly hide the static label - it's only for single-era fallback
    // cases. Without this, a leftover label from a PREVIOUSLY selected
    // single-era manager stays stuck on screen for this manager, since
    // this branch never touched it before.
    document.getElementById("era-static-label").style.display = "none";
    renderEraSection("snake", draftProfile.eras.snake);
    renderEraSection("auction", draftProfile.eras.auction);
    // Default to most recent era with data
    switchEra("auction");
  } else if (draftProfile.has_snake_era) {
    toggleWrap.style.display = "none";
    toggleWrap.innerHTML = "";
    renderEraSection("snake", draftProfile.eras.snake);
    snakeBlock.style.display = "block";
    auctionBlock.style.display = "none";
    document.getElementById("era-static-label").textContent = "SNAKE DRAFT ERA";
    document.getElementById("era-static-label").style.display = "block";
  } else if (draftProfile.has_auction_era) {
    toggleWrap.style.display = "none";
    toggleWrap.innerHTML = "";
    renderEraSection("auction", draftProfile.eras.auction);
    snakeBlock.style.display = "none";
    auctionBlock.style.display = "block";
    document.getElementById("era-static-label").textContent =
      "AUCTION DRAFT ERA";
    document.getElementById("era-static-label").style.display = "block";
  } else {
    toggleWrap.style.display = "none";
    snakeBlock.style.display = "none";
    auctionBlock.style.display = "none";
    document.getElementById("era-static-label").style.display = "none";
  }

  // Captain at the Helm + Signature Picks - unified, unaffected by era toggle
  const captainList = document.getElementById("captain-list");
  captainList.innerHTML =
    draftProfile.captain_at_the_helm && draftProfile.captain_at_the_helm.length
      ? draftProfile.captain_at_the_helm.map(buildQbItemCard).join("")
      : `<p class="item-meta">No QB picks with a known outcome found.</p>`;

  const sigList = document.getElementById("signature-picks-list");
  if (draftProfile.signature_picks && draftProfile.signature_picks.length) {
    sigList.innerHTML = draftProfile.signature_picks
      .map(
        (sp) => `
      <div class="signature-item">
        <div class="signature-name">${sp.player_name}</div>
        <div class="signature-meta">
          Drafted ${sp.times_drafted}x &middot; ${sp.years.join(", ")}<br>
          Combined: ${sp.combined_points_across_those_seasons.toFixed(2)} pts across those seasons
        </div>
      </div>
    `,
      )
      .join("");
  } else {
    sigList.innerHTML = `<p class="item-meta">No player drafted more than once by this manager.</p>`;
  }

  document.getElementById("inventory-wrap").classList.add("open");
  document
    .getElementById("inventory-wrap")
    .scrollIntoView({ behavior: "smooth" });
}

function switchEra(era) {
  document.getElementById("era-block-snake").style.display =
    era === "snake" ? "block" : "none";
  document.getElementById("era-block-auction").style.display =
    era === "auction" ? "block" : "none";
  document
    .getElementById("era-tab-snake")
    ?.classList.toggle("active", era === "snake");
  document
    .getElementById("era-tab-auction")
    ?.classList.toggle("active", era === "auction");
}

/* ============ FAQ ============ */
const FAQ_ITEMS = [
  {
    q: 'What does "value score" (snake) mean, and how is auction different?',
    a: "SNAKE ERA: value_score = total_points x round_num - rewards a late-round pick that produced real points more than the identical output from an early pick. AUCTION ERA: instead of rounds, auctions use real dollar bids, so value is measured as points-per-dollar - a $1 pick that scored 150 points is far better value than a $50 pick that scored the same 150.",
  },
  {
    q: "How are Best Steals, Stars, and Biggest Busts different from just sorting by value?",
    a: 'All three are deliberately stricter, separate categories. SNAKE: Steals = highest points among round 8+ picks. Stars = highest points among round 1-4 picks. Busts = lowest points among round 1-4 picks. AUCTION: Steals = highest points among cheap bids. Stars = highest points among expensive bids. Busts = lowest points among expensive bids. "Cheap" and "expensive" are computed dynamically each run from the real bid distribution (25th/75th percentile), not fixed dollar amounts.',
  },
  {
    q: "Why don't QBs show a rarity tag or count toward Best Value/Steals/Busts?",
    a: "QBs are excluded from BOTH eras' value systems. In snake drafts, QBs are typically drafted late but score heavily due to fantasy point weighting, which skews value_score. In auction drafts, QBs often go for a wide range of prices unrelated to points scored. Either way, QBs get their own \"Captain at the Helm\" section instead, ranked by raw total_points - unchanged across both eras, since raw points aren't biased by round or price.",
  },
  {
    q: "What determines the Legendary/Rare/Common/Junk colors?",
    a: "Both eras use the same four tier names, but computed from different underlying numbers - value_score for snake picks, points_per_dollar for auction picks - and the actual dollar/point cutoffs are recalculated fresh every time this data is regenerated, based on the real distribution that season. They are never hardcoded, so the tiers stay accurate even as more seasons get added.",
  },
  {
    q: "What does Retention Rate measure, exactly?",
    a: 'The percentage of a manager\'s draft picks that were still on THEIR OWN roster at the end of that same season, out of picks with a KNOWN outcome. It measures "still rostered at season\'s end," not "never touched all year."',
  },
  {
    q: "Why do some picks have no points or outcome shown?",
    a: "Some players were drafted, dropped, and never picked up by anyone else in the league before the season ended. Since this data only captures a snapshot of each team's FINAL roster, a player who vanished from every team's roster has no recoverable point total - not a bug, just an honest gap. Real examples: Le'Veon Bell (2018, held out the season), Michael Thomas (2020, injuries), Nick Chubb (2023, season-ending injury).",
  },
  {
    q: '"Ended With" shows a different manager than who drafted the player - what happened?',
    a: "That player was traded or claimed off waivers by someone else at some point during the season. The points shown are the player's FULL SEASON total regardless of who had them week-to-week.",
  },
  {
    q: "Why do some managers only have one era section?",
    a: "This league drafted via snake format through 2023, then switched to auction starting 2024. Anyone who joined the league in 2024 or later has only ever drafted in the auction era, and anyone who left before 2024 only ever drafted in the snake era - so their card shows just that one era, no toggle needed.",
  },
];

function renderFaq() {
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
