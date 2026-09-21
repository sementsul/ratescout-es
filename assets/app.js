var RSLOC = (function () { var L = (document.documentElement.lang || "ru").slice(0, 2); return L === "es" ? "es-AR" : (L === "en" ? "en-US" : "ru-RU"); })();
// Конвертер направления по ПОЛНОМУ каталогу BestChange (catalog.js).
// Выбор «отдаю/получаю» → CTA-ссылка на конкретное направление BestChange с реф-меткой.
(function () {
  var C = window.__CATALOG__;
  var REF = window.__REF__ || "1116359";
  var ERID = (typeof window.__ERID__ === "string") ? window.__ERID__ : "2VtzqvK5m96";
  var BCDOM = (function(){var L=(document.documentElement.lang || "ru").slice(0, 2); return L === "en" || L === "es";})()
    ? "https://www.bestchange.com" : "https://www.bestchange.ru";
  function bcQs(qs) { return ERID ? qs + "&erid=" + ERID : qs; }

  // ---- поиск по валютам (на всех страницах) ----
  (function () {
    var q = document.getElementById("q"), qres = document.getElementById("qres");
    if (!q || !qres || !C || !C.cur) return;
    var PRE = q.getAttribute("data-prefix") || "";
    var all = Object.keys(C.cur).map(function (s) {
      return { slug: s, n: C.cur[s].n, t: C.cur[s].t, key: (C.cur[s].n + " " + C.cur[s].t + " " + s).toLowerCase() };
    });
    function render(list) {
      qres.innerHTML = list.map(function (x) {
        return '<li><a href="' + PRE + '/valuta/' + x.slug + '/">' + x.n + ' <span>' + x.t + '</span></a></li>';
      }).join("");
      qres.style.display = list.length ? "block" : "none";
    }
    q.addEventListener("input", function () {
      var v = q.value.trim().toLowerCase();
      if (!v) { render([]); return; }
      render(all.filter(function (x) { return x.key.indexOf(v) >= 0; }).slice(0, 12));
    });
    q.addEventListener("keydown", function (e) {
      if (e.key === "Enter") { var a = qres.querySelector("a"); if (a) location.href = a.getAttribute("href"); }
    });
    document.addEventListener("click", function (e) {
      if (e.target !== q && !qres.contains(e.target)) render([]);
    });
  })();

  // ---- запомнить ручной выбор языка (клик по переключателю в шапке) ----
  Array.prototype.forEach.call(document.querySelectorAll(".langsw"), function (a) {
    a.addEventListener("click", function () {
      try { localStorage.setItem("rs_lang", a.getAttribute("data-lang")); } catch (e) {}
    });
  });

  // ---- сквозной поиск по ВСЕМ статьям блога (индекс встроен в страницу) ----
  (function () {
    var bq = document.getElementById("bq"), list = document.getElementById("bloglist");
    if (!bq || !list) return;
    var nores = document.getElementById("bnores");
    var pager = document.querySelector(".pager");
    var origHTML = list.innerHTML;                       // пагинированный список текущей страницы
    var INDEX = [];
    var idxEl = document.getElementById("blogIndex");
    if (idxEl) { try { INDEX = JSON.parse(idxEl.textContent); } catch (e) { INDEX = []; } }
    function esc(s) { return (s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
    bq.addEventListener("input", function () {
      var v = bq.value.trim().toLowerCase();
      if (!v) {                                          // пусто — вернуть исходную страницу + пейджер
        list.innerHTML = origHTML;
        if (pager) pager.style.display = "";
        if (nores) nores.hidden = true;
        return;
      }
      if (INDEX.length) {                                // сквозной поиск по всем статьям
        var hits = INDEX.filter(function (a) { return a.k.indexOf(v) >= 0; });
        list.innerHTML = hits.map(function (a) {
          return '<li><a href="' + a.u + '">' + esc(a.t) + '</a>' +
                 '<div class="apreview">' + esc(a.d) + '</div>' +
                 '<div class="adate">' + esc(a.dt) + '</div></li>';
        }).join("");
        if (pager) pager.style.display = "none";         // при поиске пагинация не нужна
        if (nores) nores.hidden = hits.length > 0;
      } else {                                           // фолбэк: фильтр текущей страницы
        var shown = 0;
        Array.prototype.forEach.call(list.querySelectorAll("li"), function (li) {
          var hit = (li.getAttribute("data-search") || "").indexOf(v) >= 0;
          li.style.display = hit ? "" : "none"; if (hit) shown++;
        });
        if (nores) nores.hidden = shown > 0;
      }
    });
  })();

  var conv = document.getElementById("conv");
  if (!C || !conv) return;

  var elFrom = document.getElementById("cFrom"),
      elTo = document.getElementById("cTo"),
      elGo = document.getElementById("cGo"),
      elSwap = document.getElementById("cSwap");

  // список слагов по порядку категорий
  var order = C.order || [];
  var bySlug = C.cur || {};
  var byCat = {};
  Object.keys(bySlug).forEach(function (s) {
    var c = bySlug[s].c;
    (byCat[c] = byCat[c] || []).push(s);
  });
  order.forEach(function (c) { if (byCat[c]) byCat[c].sort(function (a, b) { return bySlug[a].n.localeCompare(bySlug[b].n); }); });

  function fill(sel, selected) {
    sel.innerHTML = "";
    order.forEach(function (c) {
      var list = byCat[c]; if (!list) return;
      var og = document.createElement("optgroup"); og.label = c;
      list.forEach(function (s) {
        var o = document.createElement("option");
        o.value = s; o.textContent = bySlug[s].n + " (" + bySlug[s].t + ")";
        if (s === selected) o.selected = true;
        og.appendChild(o);
      });
      sel.appendChild(og);
    });
  }

  var presetFrom = conv.getAttribute("data-from") || "";
  var slugs = Object.keys(bySlug);
  var defFrom = presetFrom || (bySlug["zrx"] && "zrx") || slugs[0];   // без пресета «отдаю» = ZRX
  // получатель по умолчанию — популярный USDT TRC20, иначе первый отличный
  var defTo = (bySlug["tether-trc20"] && "tether-trc20") || slugs.find(function (s) { return s !== defFrom; });
  if (defTo === defFrom) defTo = slugs.find(function (s) { return s !== defFrom; });

  fill(elFrom, defFrom);
  fill(elTo, defTo);

  function deep(frm, to) { return BCDOM + "/" + frm + "-to-" + to + ".html?" + bcQs("p=" + REF); }

  var OPEN = conv.getAttribute("data-open") || "Открыть";
  var APPROX = conv.getAttribute("data-approx") || "≈";
  var SAMEMSG = OPEN === "Abrir" ? "Elegí distintas monedas" : (OPEN === "Open" ? "Choose different currencies" : "Выберите разные валюты");

  // встроенная карта лучших курсов {to: rate} для валюты-владельца (на странице валюты)
  var RATES = null, ROWNER = "", elAmt = document.getElementById("cAmt"), elOut = document.getElementById("cOut");
  var rn = document.getElementById("convRates");
  if (rn) { try { RATES = JSON.parse(rn.textContent); ROWNER = rn.getAttribute("data-owner") || ""; } catch (e) { RATES = null; } }

  // карта покрытия направлений: если для пары есть наша страница /obmen/from-to/ — ведём внутрь, иначе в BestChange.
  var CPRE = conv.getAttribute("data-prefix") || "";
  var COV = null;
  fetch(CPRE + "/pairs.json").then(function (r) { return r.json(); }).then(function (d) {
    COV = {}; var a = d.p || []; for (var i = 0; i < a.length; i++) COV[a[i]] = 1;
    if (typeof update === "function") update();
  }).catch(function () { COV = {}; });

  function fmtNum(v) {
    if (!isFinite(v)) return "";
    if (v >= 1000) return v.toLocaleString(RSLOC, { maximumFractionDigits: 0 });
    if (v >= 1) return v.toLocaleString(RSLOC, { maximumFractionDigits: 2 });
    if (v >= 0.01) return v.toFixed(4).replace(/0+$/, "").replace(/\.$/, "");
    return v.toFixed(10).replace(/0+$/, "").replace(/\.$/, "");
  }
  function estimate() {
    if (!elOut) return;
    var f = elFrom.value, t = elTo.value;
    var amt = elAmt ? parseFloat(elAmt.value) : NaN;
    // оценка возможна только для валюты-владельца встроенной карты
    if (!RATES || f !== ROWNER || !RATES[t] || !(amt >= 0)) { elOut.textContent = ""; return; }
    var got = amt * parseFloat(RATES[t]);
    elOut.innerHTML = APPROX + " <b>" + fmtNum(got) + "</b> " + bySlug[t].t;
  }

  function update() {
    var f = elFrom.value, t = elTo.value;
    if (f === t) {
      elGo.href = BCDOM + "/?" + bcQs("p=" + REF);
      elGo.setAttribute("target", "_blank"); elGo.setAttribute("rel", "nofollow noopener sponsored");
      elGo.textContent = SAMEMSG; if (elOut) elOut.textContent = ""; return;
    }
    if (COV && COV[f + "-" + t]) {                 // есть наша страница направления → ведём внутрь (не прямая реклама)
      elGo.href = CPRE + "/obmen/" + f + "-" + t + "/";
      elGo.removeAttribute("target"); elGo.setAttribute("rel", "nofollow");
    } else {                                       // страницы нет → в BestChange (реф сохраняется)
      elGo.href = deep(f, t);
      elGo.setAttribute("target", "_blank"); elGo.setAttribute("rel", "nofollow noopener sponsored");
    }
    elGo.textContent = OPEN + ": " + bySlug[f].t + " → " + bySlug[t].t + " →";
    estimate();
  }
  if (elAmt) elAmt.addEventListener("input", estimate);
  elFrom.addEventListener("change", update);
  elTo.addEventListener("change", update);
  if (elSwap) elSwap.addEventListener("click", function () {
    var a = elFrom.value; elFrom.value = elTo.value; elTo.value = a; update();
  });
  update();

  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(function () {});
})();

// ---- интерактивный график динамики цены (страницы валют) ----
(function () {
  var wrap = document.querySelector(".rschart-wrap");
  if (!wrap) return;
  var host = wrap.querySelector(".rschart"), tip = wrap.querySelector(".rstip");
  var unit = wrap.getAttribute("data-unit") || "USDT";
  var raw;
  try { raw = JSON.parse(wrap.querySelector(".rschart-data").textContent); } catch (e) { return; }
  if (!raw || raw.length < 2) return;
  function tms(s) { var p = s.split(/[- :]/); return Date.UTC(+p[0], +p[1] - 1, +p[2], +p[3] || 0, +p[4] || 0); }
  var ALL = raw.map(function (d) { return { t: tms(d[0]), v: d[1], hourly: d[0].indexOf(":") >= 0 }; });
  function fmt(v) {
    if (v >= 1000) return v.toLocaleString(RSLOC, { maximumFractionDigits: 0 });
    if (v >= 1) return v.toLocaleString(RSLOC, { maximumFractionDigits: 2 });
    if (v >= 0.01) return (+v.toFixed(4)).toString();
    return (+v.toFixed(8)).toString();
  }
  function p2(n) { return (n < 10 ? "0" : "") + n; }
  function dd(ms) { var d = new Date(ms); return { D: d.getUTCDate(), M: d.getUTCMonth() + 1, Y: d.getUTCFullYear(), h: d.getUTCHours() }; }
  function axisTime(ms, span, hourly) {
    var o = dd(ms);
    if (hourly && span <= 2 * 864e5) return p2(o.h) + ":00";   // часы — только если точки почасовые
    if (span <= 180 * 864e5) return p2(o.D) + "." + p2(o.M);    // дни
    return p2(o.M) + "." + o.Y;                                 // месяцы
  }
  function fmtDate(ms) { var o = dd(ms); return p2(o.D) + "." + p2(o.M) + "." + o.Y; }
  function fullTime(pt) {
    var o = dd(pt.t);
    return pt.hourly ? p2(o.D) + "." + p2(o.M) + "." + o.Y + " " + p2(o.h) + ":00 UTC"  // почасовая точка (с годом)
                     : p2(o.D) + "." + p2(o.M) + "." + o.Y;                             // дневная точка
  }

  var H = 220, padL = 58, padR = 12, padT = 10, padB = 26, plotH = H - padT - padB;
  var pts = [], range = "all", per = wrap.querySelector(".rsperiod");
  var RMAP = { "24h": 864e5, "7d": 7 * 864e5, "30d": 30 * 864e5, "1y": 365 * 864e5,
    "3y": 3 * 365 * 864e5, "5y": 5 * 365 * 864e5, "10y": 10 * 365 * 864e5 };
  function filtered() {
    if (range === "all" || !RMAP[range]) return ALL;
    var t1 = ALL[ALL.length - 1].t;
    var f = ALL.filter(function (d) { return d.t >= t1 - RMAP[range]; });
    return f.length >= 2 ? f : ALL;
  }
  function draw() {
    var W = Math.max(320, Math.round(host.clientWidth || 640)), plotW = W - padL - padR;
    var d = filtered(), vs = d.map(function (x) { return x.v; });
    var mn = Math.min.apply(null, vs), mx = Math.max.apply(null, vs), span = (mx - mn) || (mx || 1);
    var t0 = d[0].t, t1 = d[d.length - 1].t, tspan = (t1 - t0) || 1;
    // почасовой вид, только если в выборке есть внутридневные точки (иначе показываем дни)
    var hourly = false, j;
    for (j = 1; j < d.length; j++) { if (d[j].t - d[j - 1].t < 20 * 3600e3) { hourly = true; break; } }
    function X(t) { return padL + (t - t0) / tspan * plotW; }
    function Y(v) { return padT + (1 - (v - mn) / span) * plotH; }
    pts = d.map(function (x) { return { px: X(x.t), py: Y(x.v), v: x.v, t: x.t, hourly: x.hourly }; });
    if (per) per.textContent = ((document.documentElement.lang || "").slice(0, 2) === "es" ? "Período: " : ((document.documentElement.lang || "").slice(0, 2) === "en" ? "Period: " : "Период: ")) + fmtDate(t0) + (t0 === t1 ? "" : " — " + fmtDate(t1)) + " (UTC)";
    var s = '<svg viewBox="0 0 ' + W + ' ' + H + '" class="rssvg" width="100%" height="' + H + '">', i;
    for (i = 0; i <= 4; i++) {
      var yv = mn + span * i / 4, yy = Y(yv);
      s += '<line x1="' + padL + '" y1="' + yy.toFixed(1) + '" x2="' + (W - padR) + '" y2="' + yy.toFixed(1) + '" class="rsgrid"/>';
      s += '<text x="' + (padL - 6) + '" y="' + (yy + 3).toFixed(1) + '" class="rsylab">' + fmt(yv) + '</text>';
    }
    for (i = 0; i <= 4; i++) {
      var tt = t0 + tspan * i / 4, xx = X(tt);
      s += '<text x="' + xx.toFixed(1) + '" y="' + (H - 8) + '" class="rsxlab">' + axisTime(tt, tspan, hourly) + '</text>';
    }
    s += '<polyline fill="none" stroke="#55ff55" stroke-width="2" points="' +
      pts.map(function (p) { return p.px.toFixed(1) + "," + p.py.toFixed(1); }).join(" ") + '"/>';
    s += '<line class="rsguide" y1="' + padT + '" y2="' + (padT + plotH) + '" style="display:none"/>';
    s += '<circle class="rsdot" r="3.5" style="display:none"/></svg>';
    host.innerHTML = s;
  }
  function move(e) {
    if (!pts.length) return;
    var r = host.getBoundingClientRect(), W = Math.max(320, Math.round(host.clientWidth || 640));
    var sx = (e.clientX - r.left) / r.width * W, best = pts[0], bd = 1e9, k;
    for (k = 0; k < pts.length; k++) { var q = Math.abs(pts[k].px - sx); if (q < bd) { bd = q; best = pts[k]; } }
    var svg = host.querySelector("svg"); if (!svg) return;
    var g = svg.querySelector(".rsguide"), dot = svg.querySelector(".rsdot");
    g.setAttribute("x1", best.px); g.setAttribute("x2", best.px); g.style.display = "";
    dot.setAttribute("cx", best.px); dot.setAttribute("cy", best.py); dot.style.display = "";
    tip.innerHTML = "<b>" + fmt(best.v) + " " + unit + "</b><span>" + fullTime(best) + "</span>";
    tip.hidden = false;
    var leftPx = host.offsetLeft + best.px / W * r.width;
    tip.style.left = Math.max(0, leftPx - tip.offsetWidth / 2) + "px";
    tip.style.top = Math.max(0, host.offsetTop + best.py / H * r.height - tip.offsetHeight - 8) + "px";
  }
  function leave() {
    tip.hidden = true;
    var svg = host.querySelector("svg"); if (!svg) return;
    var g = svg.querySelector(".rsguide"), dot = svg.querySelector(".rsdot");
    if (g) g.style.display = "none"; if (dot) dot.style.display = "none";
  }
  host.addEventListener("mousemove", move);
  host.addEventListener("mouseleave", leave);
  host.addEventListener("touchmove", function (e) { if (e.touches[0]) { move(e.touches[0]); } }, { passive: true });
  Array.prototype.forEach.call(wrap.querySelectorAll(".rsrange button"), function (b) {
    b.addEventListener("click", function () {
      range = b.getAttribute("data-r");
      Array.prototype.forEach.call(wrap.querySelectorAll(".rsrange button"), function (x) { x.classList.remove("on"); });
      b.classList.add("on"); draw();
    });
  });
  var rt;
  window.addEventListener("resize", function () { clearTimeout(rt); rt = setTimeout(draw, 150); });
  draw();
})();

// ---- сортировка + период обзора графиков (/grafiki/): рост/падение за 24ч..10л ----
(function () {
  var tbl = document.querySelector(".marktbl"), sbar = document.querySelector(".sortbar"), pbar = document.querySelector(".perbar");
  if (!tbl || !sbar) return;
  var tbody = tbl.querySelector("tbody");
  var rows = Array.prototype.slice.call(tbody.querySelectorAll("tr"));
  var sortKey = "liq", period = "all";
  function liq(r) { var v = r.getAttribute("data-liq"); return v ? parseFloat(v) : 0; }
  function chg(r) {
    var v = r.getAttribute(period === "all" ? "data-chg" : "data-c" + period);
    return v === null || v === "" ? null : parseFloat(v);
  }
  function updateCol() {                       // колонка «Изм.» показывает изменение за выбранный период
    rows.forEach(function (r) {
      var cell = r.querySelector(".chg-cell"); if (!cell) return;
      var v = chg(r);
      if (v === null) { cell.innerHTML = '<span class="nd">—</span>'; return; }
      cell.innerHTML = '<b class="' + (v >= 0 ? "up" : "down") + '">' + (v >= 0 ? "+" : "") + v.toFixed(1) + '%</b>';
    });
  }
  function apply() {
    var arr = rows.slice();
    arr.sort(function (a, b) {
      if (sortKey === "liq") return liq(b) - liq(a);
      var ca = chg(a), cb = chg(b);
      if (ca === null && cb === null) return 0;
      if (ca === null) return 1;               // без изменения — в конец
      if (cb === null) return -1;
      return sortKey === "up" ? cb - ca : ca - cb;
    });
    arr.forEach(function (r) { tbody.appendChild(r); });
  }
  Array.prototype.forEach.call(sbar.querySelectorAll("button"), function (b) {
    b.addEventListener("click", function () {
      Array.prototype.forEach.call(sbar.querySelectorAll("button"), function (x) { x.classList.remove("on"); });
      b.classList.add("on"); sortKey = b.getAttribute("data-s"); apply();
    });
  });
  if (pbar) Array.prototype.forEach.call(pbar.querySelectorAll("button"), function (b) {
    b.addEventListener("click", function () {
      Array.prototype.forEach.call(pbar.querySelectorAll("button"), function (x) { x.classList.remove("on"); });
      b.classList.add("on"); period = b.getAttribute("data-p");
      updateCol();
      if (sortKey !== "liq") apply();          // пересортировать под новый период
    });
  });
})();

// ---- фильтр обзора графиков по категории (/grafiki/) ----
(function () {
  var bar = document.querySelector(".catbar"), tbl = document.querySelector(".marktbl");
  if (!bar || !tbl) return;
  var rows = Array.prototype.slice.call(tbl.querySelectorAll("tbody tr"));
  Array.prototype.forEach.call(bar.querySelectorAll("button"), function (b) {
    b.addEventListener("click", function () {
      Array.prototype.forEach.call(bar.querySelectorAll("button"), function (x) { x.classList.remove("on"); });
      b.classList.add("on");
      var f = b.getAttribute("data-f");
      rows.forEach(function (r) { r.style.display = (!f || r.getAttribute("data-cat") === f) ? "" : "none"; });
    });
  });
})();

// ---- таблица «Лучшие курсы обмена» (страница валюты): поиск по валютам-целям + категория + сортировка + период ----
(function () {
  var tbl = document.querySelector(".ratetbl"); if (!tbl) return;
  var tbody = tbl.querySelector("tbody"), inp = document.querySelector(".rtsearch");
  var cbar = document.querySelector(".rtcatbar"), sbar = document.querySelector(".rtsortbar"), pbar = document.querySelector(".rtperbar");
  var nores = document.querySelector(".rtnores");
  var ORIGINAL = Array.prototype.slice.call(tbody.querySelectorAll("tr"));
  var headers = ORIGINAL.filter(function (r) { return r.classList.contains("rtgroup"); });
  var crows = ORIGINAL.filter(function (r) { return r.classList.contains("rtrow"); });
  var query = "", cat = "", sort = "cat", period = "24h";
  function liqOf(r) { var v = r.getAttribute("data-liq"); return v ? parseFloat(v) : 0; }
  function chgOf(r) { var v = r.getAttribute("data-c" + period); return v === null || v === "" ? null : parseFloat(v); }
  function updateCol() {
    crows.forEach(function (r) {
      var cell = r.querySelector(".rtchg"); if (!cell) return;
      var v = chgOf(r);
      cell.innerHTML = v === null ? '<span class="nd">—</span>' : '<b class="' + (v >= 0 ? "up" : "down") + '">' + (v >= 0 ? "+" : "") + v.toFixed(1) + '%</b>';
    });
  }
  function catMatch(r) { return !cat || r.getAttribute("data-cat") === cat; }
  function apply() {
    if (sort === "cat" && !query) {                         // сгруппированный вид с заголовками
      ORIGINAL.forEach(function (el) { tbody.appendChild(el); });
      headers.forEach(function (h) { h.style.display = catMatch(h) ? "" : "none"; });
      crows.forEach(function (r) { r.style.display = catMatch(r) ? "" : "none"; });
      if (nores) nores.hidden = true;
    } else {                                                // плоский список: поиск/сортировка
      headers.forEach(function (h) { h.style.display = "none"; });
      var filt = crows.filter(function (r) {
        return (!query || (r.getAttribute("data-search") || "").indexOf(query) >= 0) && catMatch(r);
      });
      filt.sort(function (a, b) {
        if (sort === "up" || sort === "down") {
          var ca = chgOf(a), cb = chgOf(b);
          if (ca === null && cb === null) return liqOf(b) - liqOf(a);
          if (ca === null) return 1; if (cb === null) return -1;
          return sort === "up" ? cb - ca : ca - cb;
        }
        return liqOf(b) - liqOf(a);
      });
      crows.forEach(function (r) { r.style.display = "none"; });
      filt.forEach(function (r) { tbody.appendChild(r); r.style.display = ""; });
      if (nores) nores.hidden = filt.length > 0;
    }
    updateCol();
  }
  function wire(bar, set) {
    if (!bar) return;
    Array.prototype.forEach.call(bar.querySelectorAll("button"), function (b) {
      b.addEventListener("click", function () {
        Array.prototype.forEach.call(bar.querySelectorAll("button"), function (x) { x.classList.remove("on"); });
        b.classList.add("on"); set(b); apply();
      });
    });
  }
  if (inp) inp.addEventListener("input", function () { query = inp.value.trim().toLowerCase(); apply(); });
  wire(cbar, function (b) { cat = b.getAttribute("data-f"); });
  wire(sbar, function (b) { sort = b.getAttribute("data-s"); });
  wire(pbar, function (b) { period = b.getAttribute("data-p"); });
  updateCol();
})();

// ---- относительные (кросс-)курсы (/kursy/): база → все валюты, поиск + фильтр категорий + сортировка ----
(function () {
  var base = document.querySelector(".relbase"), body = document.querySelector(".relbody");
  if (!base || !body) return;
  var inp = document.querySelector(".relsearch"), cbar = document.querySelector(".relcat"),
    sbar = document.querySelector(".relsort"), none = document.querySelector(".relnone"), rthd = document.querySelector(".rthd");
  var PRE = base.getAttribute("data-prefix") || "";
  var ALL = [], query = "", cat = "", sort = "rate-desc", cur = {};
  function esc(x) { return (x || "").replace(/&/g, "&amp;").replace(/</g, "&lt;"); }
  function fmt(v) {
    if (!isFinite(v)) return "—";
    if (v >= 1000) return v.toLocaleString(RSLOC, { maximumFractionDigits: 0 });
    if (v >= 1) return v.toLocaleString(RSLOC, { maximumFractionDigits: 2 });
    if (v >= 0.0001) return (+v.toFixed(6)).toString();
    return v.toFixed(12).replace(/0+$/, "").replace(/\.$/, "") || "0";  // малые числа — без научной нотации
  }
  function render() {
    if (!ALL.length) return;
    var b = cur[base.value]; if (!b) return;
    if (rthd) rthd.textContent = (rthd.getAttribute("data-tpl") || "{b}").replace("{b}", b.t);
    var res = ALL.filter(function (x) {
      return x.s !== base.value && (!query || x.key.indexOf(query) >= 0) && (!cat || x.c === cat);
    }).map(function (x) { return { x: x, r: b.p / x.p }; });
    res.sort(function (a, z) {
      if (sort === "name") return a.x.n.localeCompare(z.x.n);
      return sort === "rate-asc" ? a.r - z.r : z.r - a.r;
    });
    body.innerHTML = res.map(function (o) {
      return '<tr><td class="d"><a href="' + PRE + '/valuta/' + o.x.s + '/">' + esc(o.x.n) + ' <span>' + esc(o.x.t) + '</span></a></td>' +
        '<td class="num"><b>' + fmt(o.r) + '</b> ' + esc(o.x.t) + '</td></tr>';
    }).join("");
    if (none) none.hidden = res.length > 0;
  }
  function wire(bar, set) {
    if (!bar) return;
    Array.prototype.forEach.call(bar.querySelectorAll("button"), function (btn) {
      btn.addEventListener("click", function () {
        Array.prototype.forEach.call(bar.querySelectorAll("button"), function (x) { x.classList.remove("on"); });
        btn.classList.add("on"); set(btn); render();
      });
    });
  }
  if (inp) inp.addEventListener("input", function () { query = inp.value.trim().toLowerCase(); render(); });
  base.addEventListener("change", render);
  wire(cbar, function (b) { cat = b.getAttribute("data-f"); });
  wire(sbar, function (b) { sort = b.getAttribute("data-s"); });
  fetch("/prices.json").then(function (r) { return r.json(); }).then(function (d) {
    cur = d.cur;
    ALL = Object.keys(cur).map(function (s) {
      var i = cur[s]; return { s: s, n: i.n, t: i.t, c: i.c, p: i.p, key: (i.n + " " + i.t + " " + s).toLowerCase() };
    });
    ALL.sort(function (a, b) { return a.n.localeCompare(b.n); });
    base.innerHTML = ALL.map(function (x) { return '<option value="' + x.s + '">' + esc(x.n) + ' (' + esc(x.t) + ')</option>'; }).join("");
    base.value = cur["tether-trc20"] ? "tether-trc20" : ALL[0].s;
    render();
  }).catch(function () {});
})();

// Пагинация таблицы истории в свёрнутом списке: 10 строк на страницу, кнопки 1 2 3…
(function () {
  var PER = 10;
  Array.prototype.forEach.call(document.querySelectorAll(".histbox"), function (box) {
    var tbody = box.querySelector("tbody"), pager = box.querySelector(".histpager");
    if (!tbody || !pager) return;
    var rows = Array.prototype.slice.call(tbody.querySelectorAll("tr"));
    if (rows.length <= PER) return;
    var pages = Math.ceil(rows.length / PER);
    function show(p) {
      rows.forEach(function (r, i) { r.style.display = (i >= (p - 1) * PER && i < p * PER) ? "" : "none"; });
      Array.prototype.forEach.call(pager.children, function (b) {
        b.classList.toggle("on", +b.getAttribute("data-p") === p);
      });
    }
    for (var p = 1; p <= pages; p++) {
      var b = document.createElement("button");
      b.type = "button"; b.textContent = p; b.setAttribute("data-p", p);
      b.addEventListener("click", function () { show(+this.getAttribute("data-p")); });
      pager.appendChild(b);
    }
    show(1);
  });
})();

// Полная сводная таблица «Все валюты» на /svodka/: поиск + фильтр по категориям + сортировка
(function () {
  var tbl = document.querySelector(".allcurtbl");
  if (!tbl) return;
  var tb = tbl.querySelector("tbody");
  var rows = Array.prototype.slice.call(tb.querySelectorAll("tr"));
  var inp = document.querySelector(".acsearch");
  var catbar = document.querySelector(".accat"), sortbar = document.querySelector(".acsort");
  var none = document.querySelector(".acnone");
  var q = "", cat = "", sort = "liq";
  function attr(r, k) { return r.getAttribute("data-" + k) || ""; }
  function numCmp(k, dir) {                       // NaN (нет данных) — всегда в конец
    return function (a, b) {
      var x = parseFloat(attr(a, k)), y = parseFloat(attr(b, k)), xn = isNaN(x), yn = isNaN(y);
      if (xn && yn) return 0; if (xn) return 1; if (yn) return -1; return dir * (y - x);
    };
  }
  function apply() {
    var list = rows.filter(function (r) {
      if (cat && attr(r, "cat") !== cat) return false;
      if (q && attr(r, "search").indexOf(q) < 0) return false;
      return true;
    });
    if (sort === "name") list.sort(function (a, b) { return attr(a, "name").localeCompare(attr(b, "name")); });
    else if (sort === "price") list.sort(numCmp("price", 1));
    else if (sort === "up") list.sort(numCmp("chg", 1));
    else if (sort === "down") list.sort(numCmp("chg", -1));
    else list.sort(numCmp("liq", 1));
    rows.forEach(function (r) { r.style.display = "none"; });
    list.forEach(function (r) { tb.appendChild(r); r.style.display = ""; });
    if (none) none.hidden = list.length > 0;
  }
  if (inp) inp.addEventListener("input", function () { q = inp.value.trim().toLowerCase(); apply(); });
  function wire(bar, set) {
    if (!bar) return;
    Array.prototype.forEach.call(bar.querySelectorAll("button"), function (b) {
      b.addEventListener("click", function () {
        Array.prototype.forEach.call(bar.querySelectorAll("button"), function (x) { x.classList.remove("on"); });
        b.classList.add("on"); set(b); apply();
      });
    });
  }
  wire(catbar, function (b) { cat = b.getAttribute("data-f"); });
  wire(sortbar, function (b) { sort = b.getAttribute("data-s"); });
})();
