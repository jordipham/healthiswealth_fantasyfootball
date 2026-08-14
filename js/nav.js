// JAVASCRIPT FOR SITE NAVIGATION (AUTOMATES NAV BAR)

/*
  js/nav.js

  Universal site navigation, built as a Web Component so every page just
  includes <site-nav current="managers"></site-nav> instead of duplicating
  nav HTML across every file. Add a new page? Add ONE line to the `PAGES`
  array below and every page on the site picks it up automatically.

  The `current` attribute highlights which page is active - pass the
  matching `id` from the PAGES array (e.g. current="managers").
*/

const PAGES = [
  { id: "home", label: "HOME", href: "index.html" },
  {
    id: "managers",
    label: "MANAGERS",
    href: "managers.html",
  },
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
  {
    id: "rivalries",
    label: "RIVALRY LANE",
    href: "rivalry-lane.html",
  },
  {
    id: "draft",
    label: "DRAFT DAY INVENTORY",
    href: "draft-day.html",
  },
  {
    id: "standings",
    label: "ARCHIVED STANDINGS",
    href: "standings.html",
  },
];

class SiteNav extends HTMLElement {
  connectedCallback() {
    const current = this.getAttribute("current") || "";

    const links = PAGES.map((p) => {
      const activeClass = p.id === current ? " active" : "";
      return `<a href="${p.href}" class="nav-link${activeClass}">${p.label}</a>`;
    }).join("");

    this.innerHTML = `<nav class="nav-bar">${links}</nav>`;
  }
}

customElements.define("site-nav", SiteNav);
