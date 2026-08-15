// JAVASCRIPT FOR DRAFT DAY PAGE

/*
  js/draft-day.js

  Fetches data/derived/draft_day_profiler.json and manager_profiles.json
  (the latter only for status, since draft_day_profiler.json doesn't
  carry status itself).

  RARITY THRESHOLDS - set from the real distribution of value_score
  across all picks in this file (135 samples: min 15.4, median 2745.6,
  max 5679.36). Not arbitrary - chosen to give a reasonable spread
  across all four tiers rather than one tier dominating.
*/

const DRAFT_DATA_PATH = "data/derived/draft_day_profiler.json";
const PROFILES_DATA_PATH = "data/derived/manager_profiles.json";
const PHOTO_PATH = (canonicalId) => `images/draft_day/${canonicalId}.jpg`;

/*
  RARITY THRESHOLDS - re-calibrated after QBs were excluded from this
  pool. The OLD thresholds (500/2500/4000) were set from a sample that
  included QBs, which inflate value_score structurally - once QBs were
  removed, 77% of all remaining picks fell into "Common" and
  "Legendary" nearly vanished (1 out of 939 picks). These new
  thresholds are set from the REAL non-QB distribution (939 picks):
  25th pct ~629, median ~1074, 75th pct ~1620, 90th pct ~2056.
*/
const RARITY_THRESHOLDS = { junk: 400, common: 1000, rare: 1800 };

function getRarity(valueScore) {
  if (valueScore === null || valueScore === undefined) return "common";
  if (valueScore < RARITY_THRESHOLDS.junk) return "junk";
  if (valueScore < RARITY_THRESHOLDS.common) return "common";
  if (valueScore < RARITY_THRESHOLDS.rare) return "rare";
  return "legendary";
}

const RARITY_TAG = {
  legendary: "★ LEGENDARY",
  rare: "◆ RARE",
  common: "● COMMON",
  junk: "✕ JUNK",
};

let draftData = null;
let managerProfiles = null;

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

  renderGrid();
  renderFaq();
}

function renderGrid() {
  const grid = document.getElementById("grid");

  Object.entries(managerProfiles).forEach(([canonicalId, m]) => {
    const draftProfile = draftData.manager_profiles[canonicalId];
    if (!draftProfile) return; // shouldn't happen, but don't crash if a manager has zero picks recorded

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

function buildItemCard(pick) {
  const rarity = getRarity(pick.value_score);
  const movedNote = pick.was_kept_by_drafter
    ? ""
    : `<div class="item-moved">MOVED TO: ${(pick.ended_with || []).join(" & ") || "UNKNOWN"}</div>`;

  return `
    <div class="item ${rarity}">
      <div class="rarity-tag">${RARITY_TAG[rarity]}</div>
      <div class="item-name">${pick.player_name}</div>
      <div class="item-meta">Round ${pick.round_num}, Pick ${pick.round_pick} &middot; ${pick.year}</div>
      <div class="item-points">${pick.total_points.toFixed(2)} PTS</div>
      ${movedNote}
    </div>
  `;
}

/*
  Stars get their own renderer too, same reasoning as QB cards: the
  rarity system is based on value_score, which can NEVER reward a
  round-1 pick fairly - value_score = total_points x round_num, so
  for round_num=1 that's just total_points with no multiplier at all.
  A genuinely dominant round-1 season (e.g. 370+ points) can easily
  fall into "Junk" territory, since the thresholds are calibrated
  against the whole round 1-17 pool where multipliers do the heavy
  lifting. Showing a rarity tag here would directly contradict the
  "Star" label, so this section is deliberately about raw production,
  not value-relative-to-slot.
*/
function buildStarItemCard(pick) {
  const movedNote = pick.was_kept_by_drafter
    ? ""
    : `<div class="item-moved">MOVED TO: ${(pick.ended_with || []).join(" & ") || "UNKNOWN"}</div>`;

  return `
    <div class="item star-item">
      <div class="rarity-tag">⭐ EARLY-ROUND HIT</div>
      <div class="item-name">${pick.player_name}</div>
      <div class="item-meta">Round ${pick.round_num}, Pick ${pick.round_pick} &middot; ${pick.year}</div>
      <div class="item-points">${pick.total_points.toFixed(2)} PTS</div>
      ${movedNote}
    </div>
  `;
}

/*
  QB cards get their own renderer too, deliberately WITHOUT a rarity
  tier color/tag - QBs are excluded from the Legendary/Rare/Common/
  Junk system entirely (see notes.qb_exclusion_note in the JSON), so
  showing a rarity badge here would contradict that framing.
*/
function buildQbItemCard(pick) {
  const movedNote = pick.was_kept_by_drafter
    ? ""
    : `<div class="item-moved">MOVED TO: ${(pick.ended_with || []).join(" & ") || "UNKNOWN"}</div>`;

  return `
    <div class="item qb-item">
      <div class="rarity-tag">⚡ QB SEASON</div>
      <div class="item-name">${pick.player_name}</div>
      <div class="item-meta">Round ${pick.round_num}, Pick ${pick.round_pick} &middot; ${pick.year}</div>
      <div class="item-points">${pick.total_points.toFixed(2)} PTS</div>
      ${movedNote}
    </div>
  `;
}

function showInventory(canonicalId, managerMeta, draftProfile) {
  document.getElementById("inv-name").textContent =
    `${managerMeta.owner_name.toUpperCase()} — DRAFT LOG`;

  // retention_rate = picks_kept / (picks with a KNOWN outcome), NOT
  // picks_kept / total_picks. Picks with no recoverable landing spot
  // (dropped by everyone, untraceable) are excluded from both the
  // numerator and denominator - so the displayed fraction must use
  // that same reduced denominator, or the shown numbers won't match
  // the percentage next to them.
  const knownOutcomePicks =
    draftProfile.total_picks - draftProfile.picks_with_incomplete_data;
  document.getElementById("inv-retention").textContent =
    `RETENTION RATE: ${(draftProfile.retention_rate * 100).toFixed(1)}% (${draftProfile.picks_kept}/${knownOutcomePicks} PICKS KEPT)`;
  document.getElementById("inv-incomplete").textContent =
    draftProfile.picks_with_incomplete_data > 0
      ? `${draftProfile.picks_with_incomplete_data} PICKS HAVE NO RECOVERABLE OUTCOME (DROPPED & NEVER RECLAIMED BY ANYONE) — SEE FAQ`
      : "";

  const sections = [
    {
      id: "best-value-list",
      data: draftProfile.best_value_picks,
      empty: "No complete-data picks available.",
      renderer: buildItemCard,
    },
    {
      id: "stars-list",
      data: draftProfile.stars,
      empty: "No early-round hits found (round 1-4).",
      renderer: buildStarItemCard,
    },
    {
      id: "best-steals-list",
      data: draftProfile.best_steals,
      empty: "No late-round steals found (round 8+).",
      renderer: buildItemCard,
    },
    {
      id: "biggest-busts-list",
      data: draftProfile.biggest_busts,
      empty: "No early-round busts found (round 1-4).",
      renderer: buildItemCard,
    },
    {
      id: "captain-list",
      data: draftProfile.captain_at_the_helm,
      empty: "No QB picks with a known outcome found.",
      renderer: buildQbItemCard,
    },
  ];

  sections.forEach(({ id, data, empty, renderer }) => {
    const el = document.getElementById(id);
    el.innerHTML =
      data && data.length
        ? data.map(renderer).join("")
        : `<p class="item-meta">${empty}</p>`;
  });

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

/* ============ FAQ ============ */
const FAQ_ITEMS = [
  {
    q: 'What does "value score" actually mean?',
    a: "value_score = total_points × round_num. This is a deliberate simplification, not an official stat - it rewards a late-round pick that produced real points more than the identical output from an early pick. A round-14 pick scoring 150 points ranks higher than a round-2 pick scoring the same 150, since finding that production that late is the more impressive feat.",
  },
  {
    q: "How are Best Steals and Biggest Busts different from just sorting by value score?",
    a: 'They\'re deliberately stricter, separate categories rather than opposite ends of one blended list. BEST STEALS = highest total_points among round 8+ picks only. BIGGEST BUSTS = lowest total_points among round 1-4 picks only. This isolates "found a gem late" and "reached badly early" as distinct stories, instead of mixing in irrelevant late-round dart throws that were never expected to produce anything.',
  },
  {
    q: "What's the difference between Stars and Biggest Busts?",
    a: "Same pool, opposite ends: both draw from round 1-4 non-QB picks only, since that's \"early draft capital.\" STARS = highest total_points in that pool (the pick lived up to, or exceeded, its early slot). BIGGEST BUSTS = lowest total_points in that same pool. Together they show the full range of outcomes for a manager's early-round decisions, good and bad.",
  },
  {
    q: "Why don't Stars show a rarity tag (Legendary/Rare/Common/Junk)?",
    a: 'Because value_score = total_points x round_num, a round-1 pick gets NO multiplier at all - their value_score is just their raw points. Since the rarity tiers are calibrated against the whole round 1-17 pool (where multipliers do most of the work), even a dominant round-1 season can fall into "Junk" territory by this formula, despite being one of the best performances that manager had. That\'s a real contradiction, not a display bug - so Stars gets its own badge instead of a rarity color that would actively mislead.',
  },
  {
    q: "What counts as a Signature Pick?",
    a: 'A player the same manager drafted 2 or more separate times across different years - a genuine re-draft after previously letting them go, not a keeper renewal. Matched by the player\'s unique ID, not their name, since ESPN\'s own data has real formatting inconsistencies across years (e.g. "DJ Chark" vs "DJ Chark Jr.") that would cause false negatives if matched by name alone.',
  },
  {
    q: "What does Retention Rate measure, exactly?",
    a: 'The percentage of a manager\'s draft picks that were still on THEIR OWN roster at the end of that same season. It measures "still rostered at season\'s end," not "never touched all year" - a player drafted, dropped in week 4, then re-added by the same manager in week 10 still counts as kept. It\'s a proxy for draft-day conviction and roster patience, not a perfect week-by-week loyalty tracker.',
  },
  {
    q: "Why do some picks have no points or outcome shown?",
    a: "Some players were drafted, dropped at some point in the season, and never picked up by anyone else in the league before the season ended. Since this data only captures a snapshot of each team's FINAL roster, a player who vanished from every team's roster has no recoverable point total - not a bug, just an honest gap. Real examples confirmed in this league's data: Le'Veon Bell (2018, held out the season), Michael Thomas (2020, injuries), Nick Chubb (2023, season-ending injury).",
  },
  {
    q: '"Ended With" shows a different manager than who drafted the player - what happened?',
    a: "That player was traded or claimed off waivers by someone else at some point during the season. The points shown are the player's FULL SEASON total regardless of who had them week-to-week - so this isn't necessarily \"credit\" to whoever ended with them, just an honest record of where they landed by season's end.",
  },
  {
    q: "Why don't QBs show up in Best Value, Best Steals, or Biggest Busts?",
    a: 'QBs are deliberately excluded from those three categories. QBs are typically drafted late (a common "wait on QB" strategy) but score heavily due to how fantasy points are weighted - so value_score\'s round-lateness bonus structurally favored QBs regardless of actual skill in identifying them. Nearly every "Legendary" pick was a QB before this fix, which wasn\'t a meaningful signal. QBs get their own "Captain at the Helm" section instead, ranked purely by total_points - a fair, apples-to-apples comparison between QB seasons without the round-based bias.',
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
