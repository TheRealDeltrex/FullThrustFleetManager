// The Add-system picker's filter: typing narrows the list to systems whose name or group
// contains every word typed; Enter adds the first match. The filter text survives the page
// swap after an edit (autosave.js), so several systems of one kind add in a row.
(function () {
  "use strict";
  // autosave.js re-runs the page's scripts after a swap; the handlers are bound once.
  if (window.ftSystemFilter) { window.ftSystemFilter(); return; }
  var text = "";

  function apply(picker) {
    var input = picker.querySelector(".system-filter");
    var select = picker.querySelector("select");
    input.hidden = false;
    input.value = text;
    var words = text.toLowerCase().split(/\s+/).filter(Boolean);
    var first = null;
    Array.prototype.forEach.call(select.querySelectorAll("optgroup"), function (group) {
      var shown = 0;
      Array.prototype.forEach.call(group.querySelectorAll("option"), function (o) {
        var hit = words.every(function (w) { return o.dataset.search.indexOf(w) >= 0; });
        o.hidden = !hit;
        o.disabled = !hit;
        if (hit) { shown += 1; if (!first) first = o; }
      });
      group.hidden = shown === 0;
    });
    var current = select.options[select.selectedIndex];
    if (first && (!current || current.disabled)) select.value = first.value;
    return first;
  }

  function setup() {
    document.querySelectorAll(".system-picker").forEach(apply);
  }

  document.addEventListener("input", function (event) {
    if (!event.target.classList || !event.target.classList.contains("system-filter")) return;
    text = event.target.value;
    apply(event.target.closest(".system-picker"));
  });

  document.addEventListener("keydown", function (event) {
    if (event.key !== "Enter" || !event.target.classList.contains("system-filter")) return;
    event.preventDefault();  // or the form's first button, a remove, would be pressed
    var picker = event.target.closest(".system-picker");
    if (apply(picker)) picker.querySelector("button[value=add_system]").click();
  });

  window.ftSystemFilter = setup;
  setup();
})();
