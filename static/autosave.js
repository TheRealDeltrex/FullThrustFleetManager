/* Edits take effect as they are made, with no Save or Apply button. A form marked
   data-autosave="<action>" posts itself as that action whenever one of its fields changes
   (a text field when it loses focus or on Enter), with autosave=1 so the server saves without a
   success message. A button marked data-autosave-click (add or remove a design system) takes the
   same path. The answer is swapped into the page in place, so scroll, focus and anything typed
   meanwhile stay put. Buttons without the mark (add ship, delete, ...) submit as before, and each
   form keeps its old button inside <noscript>. No network calls beyond this app. */
(function () {
  "use strict";

  var queue = [];
  var busy = false;

  function hidden(form, name, value) {
    var input = document.createElement("input");
    input.type = "hidden";
    input.name = name;
    input.value = value;
    form.appendChild(input);
  }

  // A plain submit with the action and the autosave flag as fields: the web build (whose
  // shell routes submits through Python, ftNavigate) and the fallback when a fetch fails.
  function submitPlain(form, action, url) {
    hidden(form, "action", action);
    hidden(form, "autosave", "1");
    if (url) form.setAttribute("action", url);
    HTMLFormElement.prototype.submit.call(form);
  }

  function send(form, action, url) {
    if (!form.checkValidity()) {
      form.reportValidity();
      return;
    }
    url = url || form.getAttribute("action") || location.pathname;
    if (window.ftNavigate) {
      submitPlain(form, action, url);
      return;
    }
    var data = new FormData(form);
    data.set("action", action);
    data.set("autosave", "1");
    queue.push({ form: form, action: action, url: url, data: data });
    if (!busy) next();
  }

  function next() {
    var job = queue.shift();
    if (!job) {
      busy = false;
      return;
    }
    busy = true;
    var active = document.activeElement;
    var sentValue = active && "value" in active ? active.value : null;
    fetch(job.url, { method: "POST", body: new URLSearchParams(job.data), credentials: "same-origin" })
      .then(function (response) {
        if (!response.ok) throw new Error(String(response.status));
        return response.text().then(function (html) {
          // Only the last answer is drawn: an earlier one would undo edits still on their way.
          if (!queue.length) swap(html, response.url, sentValue);
          next();
        });
      })
      .catch(function () {
        queue = [];
        busy = false;
        submitPlain(job.form, job.action, job.url);
      });
  }

  // Which field this is, by its form's place on the page, its name and which one of that name.
  function fieldKey(el) {
    if (!el || !el.form || !el.name) return null;
    var forms = Array.prototype.slice.call(document.forms);
    var same = Array.prototype.filter.call(el.form.elements, function (e) { return e.name === el.name; });
    return { form: forms.indexOf(el.form), name: el.name, index: same.indexOf(el) };
  }

  function findField(key) {
    var form = key && document.forms[key.form];
    if (!form) return null;
    var same = Array.prototype.filter.call(form.elements, function (e) { return e.name === key.name; });
    return same[key.index] || null;
  }

  function isTyped(el) {
    return el.tagName === "TEXTAREA" ||
      (el.tagName === "INPUT" && !/^(checkbox|radio|submit|button|hidden)$/i.test(el.type));
  }

  function swap(html, url, sentValue) {
    var doc = new DOMParser().parseFromString(html, "text/html");
    var active = document.activeElement;
    var key = fieldKey(active);
    var typed = active && isTyped(active) ? active.value : null;
    var caret = null;
    try { caret = typed !== null ? active.selectionStart : null; } catch (err) { /* number fields */ }
    var open = Array.prototype.map.call(document.querySelectorAll("main details"), function (d) { return d.open; });

    // The look can change from Settings, so the page takes the answer's theme too.
    if (doc.documentElement.dataset.theme) document.documentElement.dataset.theme = doc.documentElement.dataset.theme;
    ["header.topbar", "main"].forEach(function (selector) {
      var old = document.querySelector(selector);
      var fresh = doc.querySelector(selector);
      if (old && fresh) old.replaceWith(document.adoptNode(fresh));
    });
    var oldFlashes = document.querySelector(".flashes");
    if (oldFlashes) oldFlashes.remove();
    var flashes = doc.querySelector(".flashes");
    if (flashes) document.querySelector("main").before(document.adoptNode(flashes));

    // Parsed scripts do not run; recreate the page's own so their handlers come back.
    document.querySelectorAll("main script").forEach(function (old) {
      var script = document.createElement("script");
      Array.prototype.forEach.call(old.attributes, function (a) { script.setAttribute(a.name, a.value); });
      script.text = old.text;
      old.replaceWith(script);
    });
    document.querySelectorAll("main details").forEach(function (d, i) {
      if (i < open.length) d.open = open[i];
    });

    var field = findField(key);
    if (field) {
      field.focus();
      // Typed into while the save was on its way: keep the typing, which saves on blur.
      if (typed !== null && isTyped(field) && typed !== sentValue && field.value !== typed) {
        field.value = typed;
      }
      if (caret !== null) {
        try { field.setSelectionRange(caret, caret); } catch (err) { /* number fields */ }
      }
    }
    if (url && url !== location.href) history.replaceState(null, "", url);
    document.dispatchEvent(new Event("ft:swapped"));
  }

  function autosaveForm(el) {
    var form = el && el.form;
    return form && form.hasAttribute("data-autosave") && !el.hasAttribute("data-no-autosave") ? form : null;
  }

  document.addEventListener("change", function (event) {
    var form = autosaveForm(event.target);
    if (form) send(form, form.getAttribute("data-autosave"));
  });

  // Enter in a field saves it, instead of pressing the form's first button (a remove).
  document.addEventListener("keydown", function (event) {
    if (event.key !== "Enter" || event.target.tagName !== "INPUT") return;
    var form = autosaveForm(event.target);
    if (!form) return;
    event.preventDefault();
    send(form, form.getAttribute("data-autosave"));
  });

  document.addEventListener("click", function (event) {
    var button = event.target.closest && event.target.closest("button[data-autosave-click]");
    if (!button || !button.form) return;
    event.preventDefault();
    send(button.form, button.value, button.getAttribute("formaction"));
  });
})();
