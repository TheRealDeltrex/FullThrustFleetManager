// The faction pickers (templates/_factions.html): hide custom factions and other races'
// factions as the toggles say, open the name box for "New faction", and save the toggles.
(function () {
  "use strict";
  var pickers = document.querySelectorAll(".faction-picker");

  function sync(box) {
    var select = box.querySelector("select");
    var name = box.querySelector("[name=new_faction]");
    var showCustom = box.querySelector("[data-toggle=show_custom_factions]").checked;
    var showOther = box.querySelector("[data-toggle=show_other_race_factions]").checked;
    var raceSelect = box.dataset.raceFrom ? document.getElementById(box.dataset.raceFrom) : null;
    var race = raceSelect ? raceSelect.value : box.dataset.race;
    Array.prototype.forEach.call(select.options, function (o) {
      if (o.dataset.custom === undefined) return; // "No faction" and "New faction"
      var races = o.dataset.races ? o.dataset.races.split(" ") : [];
      var hide = (o.dataset.custom === "1" && !showCustom) ||
                 (!showOther && races.length > 0 && races.indexOf(race) < 0);
      if (o.dataset.keep) hide = false;
      o.hidden = hide;
      o.disabled = hide;
      if (hide && o.selected) select.value = "";
    });
    name.hidden = select.value !== "__new__";
    name.required = !name.hidden;
    if (!name.hidden && document.activeElement === select) name.focus();
  }

  pickers.forEach(function (box) {
    box.querySelector("select").addEventListener("change", function () { sync(box); });
    if (box.dataset.raceFrom) {
      var raceSelect = document.getElementById(box.dataset.raceFrom);
      if (raceSelect) raceSelect.addEventListener("change", function () { sync(box); });
    }
    box.querySelectorAll("[data-toggle]").forEach(function (toggle) {
      toggle.addEventListener("change", function () {
        // Every picker on the page follows the same toggles.
        document.querySelectorAll("[data-toggle=" + toggle.dataset.toggle + "]").forEach(function (t) {
          t.checked = toggle.checked;
        });
        pickers.forEach(sync);
        var body = new URLSearchParams();
        body.set(toggle.dataset.toggle, toggle.checked ? "1" : "0");
        fetch("/settings/factions", { method: "POST", body: body }).catch(function () {});
      });
    });
    sync(box);
  });
})();
