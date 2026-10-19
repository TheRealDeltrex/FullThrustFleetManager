/* Campaign tab: click the ship diagram to mark damage, and roll the optional repair dice.
   Everything here is a convenience: the same edits can be made with the fields below the
   diagram, so the tab works with scripting off. No network calls beyond this app. */
(function () {
  "use strict";

  // A click on a shape carrying data-ref ("hull:7", "armour:2", "system:s3") posts that ref.
  document.querySelectorAll("form[data-ssd-form]").forEach(function (form) {
    form.addEventListener("click", function (event) {
      var shape = event.target.closest("[data-ref]");
      if (!shape) return;
      form.querySelector('input[name="ref"]').value = shape.getAttribute("data-ref");
      form.submit();
    });
  });

  // Optional dice: the server rolls, so the result is one honest source (results can be typed).
  // The online version has no server to ask (data-local), so the page rolls there.
  function rollHere(sides) {
    var value = new Uint32Array(1);
    window.crypto.getRandomValues(value);
    return 1 + (value[0] % sides);
  }
  document.querySelectorAll("button[data-roll]").forEach(function (button) {
    button.addEventListener("click", function () {
      var field = button.form && button.form.querySelector(
        'input[name="' + button.getAttribute("data-target") + '"]'
      );
      var sides = parseInt(button.getAttribute("data-roll"), 10);
      if (!field || !(sides > 0)) return;
      if (button.hasAttribute("data-local")) {
        field.value = rollHere(sides);
        return;
      }
      fetch("/dice/" + sides)
        .then(function (response) {
          if (!response.ok) throw new Error(String(response.status));
          return response.text();
        })
        .then(function (value) {
          var n = parseInt(value, 10);
          if (n >= 1 && n <= sides) field.value = n;
        })
        .catch(function () { /* offline or blocked: type the result instead */ });
    });
  });
})();
