/* Shared theme control (all pages).
   The theme is set by a tiny inline <head> script first (no flash of the wrong
   ground). This wires the toggle, persists the choice, keeps the icon in sync,
   and fires `dr:themechange` so the map (app.js) can swap basemap + recolor.
   Dark is the default identity; light follows prefers-color-scheme when the user
   has not chosen. */
(function () {
  "use strict";
  const KEY = "dr_theme";

  function setIcons(theme) {
    document.querySelectorAll("[data-theme-toggle]").forEach((b) => {
      b.textContent = theme === "light" ? "☀" : "☾"; // ☀ sun / ☾ moon
      b.setAttribute("aria-pressed", theme === "light" ? "true" : "false");
      b.title = theme === "light" ? "Switch to dark" : "Switch to light";
    });
  }

  function apply(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    setIcons(theme);
    window.dispatchEvent(new CustomEvent("dr:themechange", { detail: { theme } }));
  }

  window.DR_THEME = {
    current() { return document.documentElement.getAttribute("data-theme") || "dark"; },
    toggle() {
      const next = this.current() === "light" ? "dark" : "light";
      try { localStorage.setItem(KEY, next); } catch (e) {}
      apply(next);
    },
  };

  document.addEventListener("DOMContentLoaded", () => {
    setIcons(DR_THEME.current());
    document.querySelectorAll("[data-theme-toggle]").forEach((b) =>
      b.addEventListener("click", () => DR_THEME.toggle()));
  });
})();
