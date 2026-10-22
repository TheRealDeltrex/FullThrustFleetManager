/* System icons on an editable ship diagram (.ssd-edit) are dragged to a new place. On drop the
   icon's new centre, in diagram points, goes into the diagram's hidden layout form and is posted
   through autosave.js, which pins the system there for this design. Handlers are bound to the
   document, so they outlast autosave's page swaps. */
(function () {
  "use strict";

  var drag = null;

  function point(svg, event) {
    var p = svg.createSVGPoint();
    p.x = event.clientX;
    p.y = event.clientY;
    return p.matrixTransform(svg.getScreenCTM().inverse());
  }

  document.addEventListener("pointerdown", function (event) {
    if (event.button !== 0) return;
    var group = event.target.closest && event.target.closest(".ssd-edit g.sys");
    if (!group) return;
    var svg = group.ownerSVGElement;
    event.preventDefault();
    drag = { group: group, svg: svg, start: point(svg, event), dx: 0, dy: 0 };
    group.classList.add("dragging");
    try { group.setPointerCapture(event.pointerId); } catch (err) { /* not capturable */ }
  });

  document.addEventListener("pointermove", function (event) {
    if (!drag) return;
    var p = point(drag.svg, event);
    drag.dx = p.x - drag.start.x;
    drag.dy = p.y - drag.start.y;
    drag.group.setAttribute("transform", "translate(" + drag.dx + " " + drag.dy + ")");
  });

  function finish() {
    if (!drag) return;
    var d = drag;
    drag = null;
    d.group.classList.remove("dragging");
    if (Math.abs(d.dx) < 1 && Math.abs(d.dy) < 1) {
      d.group.removeAttribute("transform");
      return;
    }
    var form = d.svg.closest(".ssd-edit").querySelector("form.ssd-layout");
    if (!form) return;
    form.elements.uid.value = d.group.dataset.uid;
    form.elements.x.value = (parseFloat(d.group.dataset.x) + d.dx).toFixed(1);
    form.elements.y.value = (parseFloat(d.group.dataset.y) + d.dy).toFixed(1);
    form.elements.uid.dispatchEvent(new Event("change", { bubbles: true }));
  }

  document.addEventListener("pointerup", finish);
  document.addEventListener("pointercancel", finish);
})();
