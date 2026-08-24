// JAVASCRIPT FOR SITE NAVIGATION (AUTOMATES NAV BAR)

/*
  js/nav.js

  Universal site navigation, built as a Web Component so every page just
  includes <site-nav current="managers"></site-nav>. Add a new page?
  Add ONE line to the PAGES array below and every page picks it up
  automatically - both the desktop nav AND the mobile hamburger menu
  are generated from this SAME array, so they can never drift out of
  sync from being hand-duplicated.

  RESPONSIVE STRATEGY (as of this rework):
  - DESKTOP (>600px): full horizontal nav bar, ANALYTICS is a
    hover-triggered dropdown - unchanged, since this was never broken
    (hover doesn't have the ambiguous tap-timing problem touch does).
  - MOBILE (<=600px): the horizontal nav bar and hover dropdown are
    HIDDEN entirely via CSS. Instead, a hamburger icon opens a
    full slide-in panel listing EVERY page as one flat list, with
    ANALYTICS as a plain section heading (not a nested toggle) above
    its 5 pages - this eliminates the floating-dropdown/tap-ambiguity
    bug mechanism completely on mobile, rather than trying to patch it.

  Both the desktop nav bar and the mobile panel are ALWAYS rendered
  into the DOM - which one is visible is controlled purely by CSS
  media queries in style.css, not by JS re-rendering on resize.
*/

const PAGES = [
  { id: "home", label: "HOME", href: "index.html" },
  { id: "managers", label: "MANAGERS", href: "managers.html" },
  {
    id: "champions",
    label: "HALL OF CHAMPIONS",
    href: "hall-of-champions.html",
  },
  {
    id: "superlatives",
    label: "LEAGUE LEADERBOARDS",
    href: "superlatives.html",
  },
  { id: "rivalries", label: "RIVALRY LANE", href: "rivalry-lane.html" },
  { id: "draft", label: "DRAFT DAY INVENTORY", href: "draft-day.html" },
  { id: "standings", label: "ARCHIVED STANDINGS", href: "standings.html" },
  {
    id: "analytics",
    label: "ANALYTICS",
    children: [
      {
        id: "analytics-performance",
        label: "PERFORMANCE PATTERNS",
        href: "analytics-performance.html",
      },
      {
        id: "analytics-draft",
        label: "DRAFT ACCURACY",
        href: "analytics-draft.html",
      },
      {
        id: "analytics-archetypes",
        label: "MANAGER ARCHETYPES",
        href: "analytics-archetypes.html",
      },
      {
        id: "analytics-rivalry",
        label: "RIVALRY ANALYTICS",
        href: "analytics-rivalry.html",
      },
      {
        id: "analytics-sim",
        label: "CHAMPIONSHIP SIM",
        href: "analytics-sim.html",
      },
    ],
  },
];

class SiteNav extends HTMLElement {
  connectedCallback() {
    const current = this.getAttribute("current") || "";

    this.innerHTML = `
      ${this.renderDesktopNav(current)}
      ${this.renderMobileTrigger()}
      ${this.renderMobilePanel(current)}
    `;

    this.wireUpDesktopDropdowns();
    this.wireUpMobilePanel();
  }

  // ============ DESKTOP: unchanged hover-dropdown nav ============
  renderDesktopNav(current) {
    const entries = PAGES.map((p) => this.renderDesktopEntry(p, current)).join(
      "",
    );
    return `<nav class="nav-bar nav-bar-desktop">${entries}</nav>`;
  }

  renderDesktopEntry(entry, current) {
    if (!entry.children) {
      const activeClass = entry.id === current ? " active" : "";
      return `<a href="${entry.href}" class="nav-link${activeClass}">${entry.label}</a>`;
    }

    const childIsActive = entry.children.some((c) => c.id === current);
    const triggerClass =
      "nav-link nav-dropdown-trigger" + (childIsActive ? " active" : "");
    const childLinks = entry.children
      .map((c) => {
        const activeClass = c.id === current ? " active" : "";
        return `<a href="${c.href}" class="nav-dropdown-item${activeClass}">${c.label}</a>`;
      })
      .join("");

    return `
      <div class="nav-dropdown">
        <span class="${triggerClass}">${entry.label} ▾</span>
        <div class="nav-dropdown-menu">${childLinks}</div>
      </div>
    `;
  }

  wireUpDesktopDropdowns() {
    // Desktop dropdown is PURE CSS :hover - see style.css. No JS
    // listener needed here at all, which is exactly why desktop was
    // never affected by the mobile tap bug in the first place.
  }

  // ============ MOBILE: hamburger trigger (hidden on desktop via CSS) ============
  renderMobileTrigger() {
    return `
      <div class="mobile-nav-bar">
        <div class="hamburger-btn" id="hamburger-btn">☰</div>
      </div>
    `;
  }

  // ============ MOBILE: slide-in panel, flat list, no nested toggle ============
  renderMobilePanel(current) {
    const rows = [];
    PAGES.forEach((entry) => {
      if (!entry.children) {
        const activeClass = entry.id === current ? " active" : "";
        rows.push(
          `<a href="${entry.href}" class="mobile-nav-link${activeClass}">${entry.label}</a>`,
        );
      } else {
        rows.push(`<div class="mobile-nav-heading">${entry.label}</div>`);
        entry.children.forEach((c) => {
          const activeClass = c.id === current ? " active" : "";
          rows.push(
            `<a href="${c.href}" class="mobile-nav-link${activeClass}">${c.label}</a>`,
          );
        });
      }
    });

    return `
      <div class="mobile-nav-backdrop" id="mobile-nav-backdrop"></div>
      <div class="mobile-nav-panel" id="mobile-nav-panel">
        <div class="mobile-nav-panel-header">
          <span>NAVIGATE</span>
          <div class="mobile-close-btn" id="mobile-close-btn">✕</div>
        </div>
        ${rows.join("")}
      </div>
    `;
  }

  wireUpMobilePanel() {
    const hamburgerBtn = this.querySelector("#hamburger-btn");
    const closeBtn = this.querySelector("#mobile-close-btn");
    const backdrop = this.querySelector("#mobile-nav-backdrop");
    const panel = this.querySelector("#mobile-nav-panel");

    const openPanel = () => {
      panel.classList.add("open");
      backdrop.classList.add("show");
    };
    const closePanel = () => {
      panel.classList.remove("open");
      backdrop.classList.remove("show");
    };

    hamburgerBtn.addEventListener("click", openPanel);
    closeBtn.addEventListener("click", closePanel);
    backdrop.addEventListener("click", closePanel);
  }
}

customElements.define("site-nav", SiteNav);
