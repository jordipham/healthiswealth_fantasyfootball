// JAVASCRIPT FOR SITE NAVIGATION (AUTOMATES NAV BAR)

/*
  js/nav.js

  Universal site navigation, built as a Web Component so every page just
  includes <site-nav current="managers"></site-nav> instead of duplicating
  nav HTML across every file. Add a new page? Add ONE line to the `PAGES`
  array below and every page on the site picks it up automatically.

  The `current` attribute highlights which page is active - pass the
  matching `id` from the PAGES array (e.g. current="managers"), or the
  matching CHILD id for a dropdown entry (e.g. current="analytics-draft").

  DROPDOWN SUPPORT: an entry with a `children` array (instead of `href`)
  renders as a dropdown trigger, not a direct link. Two independent
  interaction paths handle showing/hiding it:
    - DESKTOP: pure CSS :hover (see css/style.css) - zero JS needed.
    - MOBILE/TOUCH: JS click-to-toggle (below), since touch devices
      don't have a real hover state. A tap-outside-to-close listener
      is also wired up so the menu doesn't stay stuck open.
  Both paths target the same markup - there's no separate mobile nav.
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
    this.innerHTML = `<nav class="nav-bar">${PAGES.map((p) => this.renderEntry(p, current)).join("")}</nav>`;
    this.wireUpDropdowns();
  }

  renderEntry(entry, current) {
    if (!entry.children) {
      const activeClass = entry.id === current ? " active" : "";
      return `<a href="${entry.href}" class="nav-link${activeClass}">${entry.label}</a>`;
    }

    // Dropdown entry: trigger is active if the CURRENT page is any of its children
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

  wireUpDropdowns() {
    const dropdowns = this.querySelectorAll(".nav-dropdown");

    dropdowns.forEach((dropdown) => {
      const trigger = dropdown.querySelector(".nav-dropdown-trigger");

      // MOBILE/TOUCH path: click toggles the .open class, which a CSS
      // rule (separate from the :hover rule) also reveals the menu for.
      trigger.addEventListener("click", (e) => {
        e.stopPropagation(); // don't let this click also trigger the outside-click closer below
        const isOpen = dropdown.classList.contains("open");
        // Close any other open dropdowns first (only one open at a time)
        dropdowns.forEach((d) => d.classList.remove("open"));
        if (!isOpen) dropdown.classList.add("open");
      });
    });

    // Tap/click anywhere outside a dropdown closes it - touch has no
    // equivalent of "mouse moved away", so this is required for mobile.
    document.addEventListener("click", () => {
      dropdowns.forEach((d) => d.classList.remove("open"));
    });
  }
}

customElements.define("site-nav", SiteNav);
