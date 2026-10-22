/* Clicks keep the view. Most buttons post and the answer is a fresh page, which would open at
   the top; so every click, change, Enter and page exit notes where this page is scrolled, and a
   page that opens on the same path scrolls back there. The path comes from <html data-path>,
   since the online version draws pages into a frame that has no path of its own. A message
   shown while scrolled down floats at the top so it is still seen. No network calls. */
(function () {
  "use strict";

  var STORE = "ft-scroll";
  var FRESH_MS = 30000;

  function path() {
    return document.documentElement.getAttribute("data-path") || location.pathname;
  }

  function note() {
    try {
      sessionStorage.setItem(STORE, JSON.stringify({ path: path(), x: window.scrollX, y: window.scrollY, t: Date.now() }));
    } catch (err) { /* storage blocked */ }
  }

  ["click", "change", "submit"].forEach(function (type) {
    document.addEventListener(type, note, true);
  });
  document.addEventListener("keydown", function (event) {
    if (event.key === "Enter") note();
  }, true);
  window.addEventListener("pagehide", note);

  function float() {
    var flashes = document.querySelector(".flashes");
    if (!flashes || window.scrollY < 40) return;
    flashes.classList.add("floating");
    flashes.addEventListener("click", function () { flashes.remove(); });
    if (!flashes.querySelector(".flash.error")) {
      setTimeout(function () { flashes.remove(); }, 4000);
    }
  }

  function restore() {
    var saved = null;
    try { saved = JSON.parse(sessionStorage.getItem(STORE)); } catch (err) { /* storage blocked */ }
    // A link to a #section scrolls there itself.
    if (!saved || location.hash || saved.path !== path() || Date.now() - saved.t > FRESH_MS) return;
    window.scrollTo(saved.x, saved.y);
    // Pictures can still be loading and change the height; scroll again once they are in.
    window.addEventListener("load", function () {
      if (window.scrollY !== saved.y) window.scrollTo(saved.x, saved.y);
    }, { once: true });
    float();
  }

  if ("scrollRestoration" in history) history.scrollRestoration = "manual";
  restore();
  document.addEventListener("ft:swapped", float);
})();
