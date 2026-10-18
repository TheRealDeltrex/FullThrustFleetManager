/* Left-pane sections fold down to their header. A header marked data-fold="<key>" toggles the
   section after it; the folded keys are kept in this browser's storage, so a section stays
   folded across reloads, and autosave.js asks for them again after it swaps the page in place. */
(function () {
  "use strict";

  var STORE = "ft-folded";

  function load() {
    try { return JSON.parse(localStorage.getItem(STORE)) || []; } catch (err) { return []; }
  }

  function save(keys) {
    try { localStorage.setItem(STORE, JSON.stringify(keys)); } catch (err) { /* storage blocked */ }
  }

  function mark() {
    var folded = load();
    document.querySelectorAll("[data-fold]").forEach(function (h) {
      h.setAttribute("aria-expanded", folded.indexOf(h.dataset.fold) < 0 ? "true" : "false");
    });
  }

  function toggle(h) {
    var key = h.dataset.fold;
    var keys = load().filter(function (k) { return k !== key; });
    if (h.getAttribute("aria-expanded") !== "false") keys.push(key);
    save(keys);
    mark();
  }

  document.addEventListener("click", function (e) {
    var h = e.target.closest && e.target.closest("[data-fold]");
    if (h) toggle(h);
  });
  document.addEventListener("keydown", function (e) {
    var h = e.target.closest && e.target.closest("[data-fold]");
    if (h && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); toggle(h); }
  });
  document.addEventListener("ft:swapped", mark);
  mark();
})();
