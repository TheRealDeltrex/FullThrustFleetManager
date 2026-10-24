/* Ships in a squadron are reordered by dragging a card by its handle, within the squadron or
   into another one; the arrow keys on a focused handle move it one place. The new order is
   posted through autosave.js as soon as the card is dropped (the squadron's hidden ship-order
   form). Handlers are bound to the document, so they outlast autosave's page swaps. Touch and pen
   drags skip the browser's drag and drop, which most tablets lack: the card follows the finger,
   and the page scrolls when it nears the top or bottom edge. */
(function () {
  "use strict";

  var dragged = null;
  var home = null;
  var dropped = false;
  var refocus = null;

  function save(list) {
    var form = list.closest(".panel").querySelector("form.ship-order");
    if (!form) return;
    var order = form.elements.order;
    order.value = Array.prototype.map.call(list.querySelectorAll(".card[data-uid]"),
      function (c) { return c.dataset.uid; }).join(",");
    order.dispatchEvent(new Event("change", { bubbles: true }));
  }

  // The card the pointer is over or nearest to, and whether to go after it.
  function target(list, x, y) {
    var best = null, dist = Infinity, after = false;
    list.querySelectorAll(".card[data-uid]").forEach(function (c) {
      if (c === dragged) return;
      var r = c.getBoundingClientRect();
      var dx = Math.max(r.left - x, 0, x - r.right), dy = Math.max(r.top - y, 0, y - r.bottom);
      var d = dx * dx + dy * dy;
      if (d < dist) {
        dist = d;
        best = c;
        after = y > r.bottom || (y >= r.top && x > r.left + r.width / 2);
      }
    });
    return { card: best, after: after };
  }

  // Puts the dragged card where the pointer is over a squadron's list.
  function place(list, x, y) {
    var t = target(list, x, y);
    if (!t.card) list.appendChild(dragged);
    else if (t.after) t.card.after(dragged);
    else t.card.before(dragged);
  }

  var touch = null;

  function scroll() {
    if (!touch) return;
    var edge = 60, h = window.innerHeight;
    if (touch.y < edge) window.scrollBy(0, -Math.ceil((edge - touch.y) / 4));
    else if (touch.y > h - edge) window.scrollBy(0, Math.ceil((touch.y - h + edge) / 4));
    requestAnimationFrame(scroll);
  }

  function endTouch(cancelled) {
    var card = dragged;
    touch = null;
    dragged = null;
    card.classList.remove("dragging");
    if (cancelled) home.parent.insertBefore(card, home.next);
    else if (card.parentNode !== home.parent || card.nextSibling !== home.next) save(card.parentNode);
  }

  document.addEventListener("pointerdown", function (event) {
    var handle = event.target.closest && event.target.closest(".drag-handle");
    if (!handle) return;
    var card = handle.closest(".card");
    if (event.pointerType === "mouse") {
      card.draggable = true;
      return;
    }
    if (touch || !card.matches(".card[data-uid]")) return;
    event.preventDefault();
    dragged = card;
    home = { parent: card.parentNode, next: card.nextSibling };
    touch = { id: event.pointerId, y: event.clientY };
    card.classList.add("dragging");
    requestAnimationFrame(scroll);
  });

  document.addEventListener("pointermove", function (event) {
    if (!touch || event.pointerId !== touch.id) return;
    event.preventDefault();
    touch.y = event.clientY;
    var under = document.elementFromPoint(event.clientX, event.clientY);
    var list = under && under.closest(".cards[data-squadron]");
    if (list) place(list, event.clientX, event.clientY);
  });

  document.addEventListener("pointerup", function (event) {
    if (touch && event.pointerId === touch.id) return endTouch(false);
    document.querySelectorAll(".card[draggable]").forEach(function (c) {
      if (c !== dragged) c.removeAttribute("draggable");
    });
  });

  document.addEventListener("pointercancel", function (event) {
    if (touch && event.pointerId === touch.id) endTouch(true);
  });

  document.addEventListener("dragstart", function (event) {
    var card = event.target.closest && event.target.closest(".card[data-uid][draggable]");
    if (!card) return;
    dragged = card;
    home = { parent: card.parentNode, next: card.nextSibling };
    dropped = false;
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", card.dataset.uid);
    setTimeout(function () { card.classList.add("dragging"); }, 0);
  });

  document.addEventListener("dragover", function (event) {
    var list = dragged && event.target.closest && event.target.closest(".cards[data-squadron]");
    if (!list) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
    place(list, event.clientX, event.clientY);
  });

  document.addEventListener("drop", function (event) {
    var list = dragged && event.target.closest && event.target.closest(".cards[data-squadron]");
    if (!list) return;
    event.preventDefault();
    dropped = true;
    var moved = dragged.parentNode !== home.parent || dragged.nextSibling !== home.next;
    if (moved) save(list);
  });

  document.addEventListener("dragend", function () {
    if (!dragged) return;
    dragged.classList.remove("dragging");
    dragged.removeAttribute("draggable");
    if (!dropped) home.parent.insertBefore(dragged, home.next);
    dragged = null;
  });

  document.addEventListener("keydown", function (event) {
    var handle = event.target.closest && event.target.closest(".drag-handle");
    if (!handle) return;
    var back = event.key === "ArrowUp" || event.key === "ArrowLeft";
    var on = event.key === "ArrowDown" || event.key === "ArrowRight";
    if (!back && !on) return;
    event.preventDefault();
    var card = handle.closest(".card");
    var other = back ? card.previousElementSibling : card.nextElementSibling;
    if (!other || !other.matches(".card[data-uid]")) return;
    if (back) other.before(card); else other.after(card);
    handle.focus();
    refocus = card.dataset.uid;
    save(card.parentNode);
  });

  document.addEventListener("ft:swapped", function () {
    if (!refocus) return;
    var handle = document.querySelector('.card[data-uid="' + refocus + '"] .drag-handle');
    refocus = null;
    if (handle) handle.focus();
  });
})();
