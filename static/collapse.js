/* Panel sections fold down to their header. A header marked data-fold="<key>" toggles what
   follows it up to the next header; the folded keys are kept in this browser's storage, so a
   section stays folded across reloads, and autosave.js asks for them again after it swaps the
   page in place. */
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
      var open = folded.indexOf(h.dataset.fold) < 0;
      h.setAttribute("aria-expanded", open ? "true" : "false");
      for (var el = h.nextElementSibling; el && el.tagName !== "H3"; el = el.nextElementSibling) {
        el.classList.toggle("folded", !open);
      }
    });
  }

  function toggle(h) {
    var key = h.dataset.fold;
    var keys = load().filter(function (k) { return k !== key; });
    if (h.getAttribute("aria-expanded") !== "false") keys.push(key);
    save(keys);
    mark();
  }

  // A link to a folded section (#fleet-details, or a page opened at one) opens it.
  function reveal(id) {
    var target = id && document.getElementById(id);
    var shut = target && target.querySelector('[data-fold][aria-expanded="false"]');
    if (shut) toggle(shut);
  }

  document.addEventListener("click", function (e) {
    var h = e.target.closest && e.target.closest("[data-fold]");
    if (h) return toggle(h);
    var a = e.target.closest && e.target.closest('a[href^="#"]');
    if (a && a.hash) reveal(a.hash.slice(1));
  });
  document.addEventListener("keydown", function (e) {
    var h = e.target.closest && e.target.closest("[data-fold]");
    if (h && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); toggle(h); }
  });
  document.addEventListener("ft:swapped", mark);
  mark();
  reveal(location.hash.slice(1));
})();
