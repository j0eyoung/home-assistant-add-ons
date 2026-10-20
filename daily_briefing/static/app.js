(function () {
  "use strict";
  var grid = document.getElementById("grid");
  var statusEl = document.getElementById("status");
  var dateEl = document.getElementById("date");

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  function card(s) {
    var c = el("section", "card " + s.status);
    c.appendChild(el("h2", null, s.title));
    c.appendChild(el("div", "head", s.headline));
    var ul = el("ul");
    // the first line repeats the headline for most sections; Today's first line is the date, shown in the page header
    (s.lines || []).forEach(function (l, i) {
      if (i === 0 && (s.key === "today" || (l && s.headline.indexOf(l) === 0))) return;
      var li = el("li", l ? null : "gap", l);
      ul.appendChild(li);
    });
    c.appendChild(ul);
    return c;
  }

  function render(d) {
    dateEl.textContent = d.date;
    var t = new Date(d.updated);
    statusEl.textContent = "Updated " + (isNaN(t) ? d.updated : t.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }));
    grid.textContent = "";
    d.sections.forEach(function (s) { grid.appendChild(card(s)); });
  }

  function load() {
    fetch("api/briefing", { cache: "no-store" })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(render)
      .catch(function () { statusEl.textContent = "Cannot reach the add-on. Retrying…"; });
  }

  load();
  setInterval(load, 30000);

  document.getElementById("copy").addEventListener("click", function () {
    fetch("api/dashboard.yaml").then(function (r) { return r.text(); }).then(function (txt) {
      return navigator.clipboard.writeText(txt);
    }).then(function () {
      var c = document.getElementById("copied");
      c.hidden = false;
      setTimeout(function () { c.hidden = true; }, 2500);
    }).catch(function () { statusEl.textContent = "Could not copy. Open api/dashboard.yaml and copy it by hand."; });
  });
})();
