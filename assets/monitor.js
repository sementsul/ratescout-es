/* RateScout — профессиональный монитор: графики многих валют на одной шкале.
   Данные: /data/monitor.json (series: курс валюты в USDT по датам). База по умолчанию — доллар (USDT).
   Ре-база: делим ряды на ряд базовой валюты. Много валют → индекс (старт=100) для сравнимости; одна → цена в базе.
   Типы: линии / свечи (по одной валюте, OHLC из точек дня) / пара A/B (отношение двух валют).
   Плюс: % изменения, пресеты групп, лог-шкала, статистика, матрица корреляций, экспорт CSV/PNG, ссылка на состояние.
   Всё в SVG, без внешних библиотек. */
(function () {
  var root = document.getElementById("monitor");
  if (!root) return;
  var host = document.getElementById("monChart");
  var listEl = document.getElementById("monList");
  var baseSel = document.getElementById("monBase");
  var typeSel = document.getElementById("monType");
  var rangesEl = document.getElementById("monRanges");
  var searchEl = document.getElementById("monSearch");
  var legEl = document.getElementById("monLegend");
  var noteEl = document.getElementById("monNote");
  var clearEl = document.getElementById("monClear");
  var logEl = document.getElementById("monLog");
  var corrChk = document.getElementById("monCorrChk");
  var statsEl = document.getElementById("monStats");
  var corrEl = document.getElementById("monCorrBox");
  var presetsEl = document.getElementById("monPresets");
  var csvBtn = document.getElementById("monCsv");
  var pngBtn = document.getElementById("monPng");
  var linkBtn = document.getElementById("monLink");
  var catsEl = document.getElementById("monCats");
  var showSel = document.getElementById("monShow");

  var LANG = (document.documentElement.getAttribute("lang") || "ru").slice(0, 2);
  var EN = LANG === "en";
  function T(ru, en, es) { return LANG === "es" ? (es === undefined ? en : es) : (EN ? en : ru); }
  function LOC() { return LANG === "es" ? "es-AR" : (EN ? "en-US" : "ru-RU"); }

  var DATA = null, checked = {}, base = "USD", type = "line", sel = 0, logScale = false, showCorr = false;
  var catFilter = "", showMode = "all";
  var HOVER = null, tipEl = null, crossEl = null;
  var COLORS = ["#3399dd", "#33cc99", "#cc9944", "#cc5588", "#7a5cd0", "#5cc0d0", "#d05c8a", "#9ad04a",
                "#d0a24a", "#4ad0a2", "#d04a4a", "#4a7ad0", "#cdd04a", "#d04acd"];
  var RANGES = [{ k: 7, l: T("Неделя", "Week", "Semana") }, { k: 30, l: T("Месяц", "Month", "Mes") }, { k: 90, l: "3 " + T("мес", "mo", "mes") },
                { k: 180, l: "6 " + T("мес", "mo", "mes") }, { k: 365, l: T("Год", "Year", "Año") }, { k: 1095, l: "3 " + T("года", "yr", "años") },
                { k: 1825, l: "5 " + T("лет", "yr", "años") }, { k: 3650, l: "10 " + T("лет", "yr", "años") }];
  // группы для быстрых пресетов
  var TOP_CRYPTO = ["bitcoin", "ethereum", "ripple", "litecoin", "dogecoin", "monero", "tron", "bitcoin-cash", "dash", "zcash", "cardano", "solana", "polkadot"];
  var STABLE_T = ["USDT", "USDC", "DAI", "BUSD", "TUSD", "USDP", "FDUSD", "USDD"];
  var FIAT_T = ["USD", "EUR", "RUB", "GBP", "UAH", "KZT", "TRY", "CNY", "JPY", "BYN"];

  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function dnum(s) { var p = s.slice(0, 10).split("-"); return Date.UTC(+p[0], +p[1] - 1, +p[2]) / 86400000 + (s.length > 10 ? (+s.slice(11, 13)) / 24 : 0); }
  function fmtDate(s) { return s.slice(8, 10) + "." + s.slice(5, 7); }
  function fmtNum(v) { if (v == null || isNaN(v)) return "—"; var a = Math.abs(v); if (a >= 1000) return Math.round(v).toLocaleString(LOC()); if (a >= 1) return v.toFixed(2); if (a >= 0.01) return v.toFixed(4); return v.toPrecision(3); }
  function fmtPct(p) { if (p == null || isNaN(p)) return ""; return (p >= 0 ? "+" : "") + p.toFixed(1) + "%"; }
  function name(s) { return (DATA.cur[s] || {}).n || s; }
  function ticker(s) { return (DATA.cur[s] || {}).t || ""; }
  function baseName() { return base === "USD" ? "USDT" : ticker(base); }

  fetch("/data/monitor.json").then(function (r) { return r.json(); }).then(function (j) {
    DATA = j;
    var slugs = Object.keys(j.series);
    baseSel.innerHTML = '<option value="USD">' + T("Доллар (USDT)", "Dollar (USDT)", "Dólar (USDT)") + "</option>" +
      slugs.slice().sort(byName).map(function (s) { var c = j.cur[s] || { n: s, t: "" }; return '<option value="' + s + '">' + esc(c.n) + " (" + esc(c.t) + ")</option>"; }).join("");
    // состояние из URL, иначе дефолт
    if (!readURL()) {
      ["bitcoin", "ethereum", "litecoin", "monero", "tron", "ripple", "dogecoin"].filter(function (s) { return j.series[s]; }).slice(0, 4).forEach(function (s) { checked[s] = 1; });
      if (!Object.keys(checked).length) slugs.slice(0, 4).forEach(function (s) { checked[s] = 1; });
    }
    baseSel.value = base; typeSel.value = type; logEl.checked = logScale; corrChk.checked = showCorr;
    buildPresets(); buildCats(); buildList(""); buildRanges(); draw();
  }).catch(function () { if (noteEl) noteEl.textContent = T("Не удалось загрузить данные монитора.", "Failed to load monitor data.", "No se pudieron cargar los datos del monitor."); });

  function byName(a, b) { return (DATA.cur[a] ? DATA.cur[a].n : a) > (DATA.cur[b] ? DATA.cur[b].n : b) ? 1 : -1; }

  // ---------- состояние в URL ----------
  function readURL() {
    var q = new URLSearchParams(location.search);
    if (![].concat.apply([], ["base", "type", "range", "cur", "log", "corr"].map(function (k) { return q.has(k) ? [1] : []; })).length) return false;
    if (q.get("base")) base = q.get("base");
    if (q.get("type")) type = q.get("type");
    if (q.get("range")) sel = +q.get("range") || 0;
    logScale = q.get("log") === "1";
    showCorr = q.get("corr") === "1";
    var cur = q.get("cur");
    if (cur) { checked = {}; cur.split(",").forEach(function (s) { if (DATA.series[s]) checked[s] = 1; }); }
    return true;
  }
  function writeURL() {
    var q = new URLSearchParams();
    if (base !== "USD") q.set("base", base);
    if (type !== "line") q.set("type", type);
    if (sel) q.set("range", sel);
    if (logScale) q.set("log", "1");
    if (showCorr) q.set("corr", "1");
    var cur = selected(); if (cur.length) q.set("cur", cur.join(","));
    var s = q.toString();
    history.replaceState(null, "", location.pathname + (s ? "?" + s : ""));
  }

  // ---------- пресеты групп ----------
  function resolveGroup(g) {
    if (g === "top") return TOP_CRYPTO.filter(function (s) { return DATA.series[s]; }).slice(0, 8);
    var set = g === "stable" ? STABLE_T : FIAT_T;
    return Object.keys(DATA.series).filter(function (s) { return set.indexOf(ticker(s)) >= 0; }).sort(byName).slice(0, 8);
  }
  function buildPresets() {
    var defs = [{ g: "top", l: T("Топ-крипта", "Top crypto", "Top cripto") }, { g: "stable", l: T("Стейблы", "Stables", "Stables") }, { g: "fiat", l: T("Фиат", "Fiat", "Fiat") }];
    presetsEl.innerHTML = defs.map(function (d) {
      var n = resolveGroup(d.g).length;
      return n ? '<button class="mon-btn" data-g="' + d.g + '">' + d.l + " <b>" + n + "</b></button>" : "";
    }).join("");
    Array.prototype.forEach.call(presetsEl.querySelectorAll("button"), function (b) {
      b.addEventListener("click", function () {
        checked = {}; resolveGroup(b.getAttribute("data-g")).forEach(function (s) { checked[s] = 1; });
        buildList(searchEl.value); buildRanges(); draw(); writeURL();
      });
    });
  }

  // ---------- фильтр по категориям (как на /svodka/) ----------
  function buildCats() {
    if (!catsEl || !DATA.cats) return;
    var all = '<button type="button" data-c=""' + (catFilter ? "" : ' class="on"') + ">" + T("Все", "All", "Todas") + "</button>";
    catsEl.innerHTML = all + DATA.cats.map(function (c) {
      return '<button type="button" data-c="' + c.s + '"' + (catFilter === c.s ? ' class="on"' : "") + ">" + esc(LANG === "es" ? (c.es || c.en) : (EN ? c.en : c.ru)) + "</button>";
    }).join("");
    Array.prototype.forEach.call(catsEl.querySelectorAll("button"), function (b) {
      b.addEventListener("click", function () {
        catFilter = b.getAttribute("data-c");
        Array.prototype.forEach.call(catsEl.querySelectorAll("button"), function (x) { x.classList.toggle("on", x.getAttribute("data-c") === catFilter); });
        buildList(searchEl.value);
      });
    });
  }

  // ---------- список валют (с % за период) ----------
  function buildList(q) {
    q = (q || "").toLowerCase().trim();
    var slugs = Object.keys(DATA.series).filter(function (s) {
      if (showMode === "sel" && !checked[s]) return false;
      if (catFilter && (DATA.cur[s] || {}).cs !== catFilter) return false;
      if (!q) return true;
      var c = DATA.cur[s] || {};
      return (s + " " + (c.n || "") + " " + (c.t || "")).toLowerCase().indexOf(q) >= 0;
    }).sort(byName);
    if (!slugs.length) { listEl.innerHTML = '<p class="mon-empty">' + T("Ничего не найдено", "Nothing found", "Nada encontrado") + "</p>"; return; }
    listEl.innerHTML = slugs.map(function (s) {
      var c = DATA.cur[s] || { n: s, t: "" }, pc = pctChange(s);
      var badge = pc == null ? "" : '<em class="mon-pc ' + (pc >= 0 ? "up" : "dn") + '">' + fmtPct(pc) + "</em>";
      return '<label class="mon-item"><input type="checkbox" data-s="' + esc(s) + '"' + (checked[s] ? " checked" : "") + '> ' +
        '<span>' + esc(c.n) + ' <b>' + esc(c.t) + "</b></span>" + badge + "</label>";
    }).join("");
    Array.prototype.forEach.call(listEl.querySelectorAll("input"), function (inp) {
      inp.addEventListener("change", function () { var s = inp.getAttribute("data-s"); if (inp.checked) checked[s] = 1; else delete checked[s]; buildRanges(); draw(); writeURL(); if (showMode === "sel") buildList(searchEl.value); });
    });
  }

  function selected() { return Object.keys(checked).filter(function (s) { return DATA.series[s]; }); }

  // ряд валюты в базовой валюте: [[date, value], ...]
  function rebased(slug) {
    var s = DATA.series[slug];
    if (base === "USD") return s.slice();
    var b = DATA.series[base]; if (!b) return s.slice();
    var bm = {}; b.forEach(function (p) { bm[p[0]] = p[1]; });
    var out = [];
    s.forEach(function (p) { var bv = bm[p[0]]; if (bv) out.push([p[0], p[1] / bv]); });
    return out;
  }
  // отношение A/B из сырых USDT-рядов (не зависит от базы)
  function ratioSeries(a, b) {
    var A = DATA.series[a], B = DATA.series[b]; if (!A || !B) return [];
    var bm = {}; B.forEach(function (p) { bm[p[0]] = p[1]; });
    var out = []; A.forEach(function (p) { var bv = bm[p[0]]; if (bv) out.push([p[0], p[1] / bv]); });
    return out;
  }
  function rangeFilter(pts) {
    if (!sel || pts.length < 2) return pts;
    var last = dnum(pts[pts.length - 1][0]) - sel;
    return pts.filter(function (p) { return dnum(p[0]) >= last; });
  }
  // % изменения валюты за текущий диапазон (в базе)
  function pctChange(slug) {
    var p = rangeFilter(rebased(slug)); if (p.length < 2) return null;
    var a = p[0][1], b = p[p.length - 1][1]; if (!a) return null; return (b / a - 1) * 100;
  }
  function spanDays() {
    var mx = 0;
    selected().forEach(function (s) { var p = DATA.series[s]; if (p.length > 1) mx = Math.max(mx, dnum(p[p.length - 1][0]) - dnum(p[0][0])); });
    return mx;
  }
  function buildRanges() {
    var span = spanDays();
    var av = RANGES.filter(function (r) { return span >= r.k; });
    var btns = av.concat([{ k: 0, l: T("Всё", "All", "Todo") }]);
    if (!av.some(function (r) { return r.k === sel; }) && sel !== 0) sel = av.length ? av[av.length - 1].k : 0;
    rangesEl.innerHTML = btns.map(function (r) { return '<button class="mon-btn" data-k="' + r.k + '">' + r.l + "</button>"; }).join("");
    Array.prototype.forEach.call(rangesEl.querySelectorAll(".mon-btn"), function (b) {
      b.addEventListener("click", function () { sel = +b.getAttribute("data-k"); markR(); buildList(searchEl.value); draw(); writeURL(); });
    });
    markR();
  }
  function markR() { Array.prototype.forEach.call(rangesEl.querySelectorAll(".mon-btn"), function (b) { b.classList.toggle("on", +b.getAttribute("data-k") === sel); }); }

  baseSel.addEventListener("change", function () { base = baseSel.value; buildList(searchEl.value); buildRanges(); draw(); writeURL(); });
  typeSel.addEventListener("change", function () { type = typeSel.value; draw(); writeURL(); });
  logEl.addEventListener("change", function () { logScale = logEl.checked; draw(); writeURL(); });
  corrChk.addEventListener("change", function () { showCorr = corrChk.checked; draw(); writeURL(); });
  searchEl.addEventListener("input", function () { buildList(searchEl.value); });
  if (showSel) showSel.addEventListener("change", function () { showMode = showSel.value; buildList(searchEl.value); });
  if (clearEl) clearEl.addEventListener("click", function () { checked = {}; buildList(searchEl.value); draw(); writeURL(); });
  if (csvBtn) csvBtn.addEventListener("click", exportCSV);
  if (pngBtn) pngBtn.addEventListener("click", exportPNG);
  if (linkBtn) linkBtn.addEventListener("click", copyLink);

  // ---------- масштаб оси Y (линейный/лог) ----------
  function makeScale(mn, mx, log, padT, h) {
    if (log && mn <= 0) log = false;
    var lmn = log ? Math.log(mn) / Math.LN10 : mn, lmx = log ? Math.log(mx) / Math.LN10 : mx;
    if (lmn === lmx) { lmx = lmn + 1; }
    return {
      log: log,
      Y: function (v) { var t = log ? Math.log(v) / Math.LN10 : v; return padT + h - (t - lmn) / (lmx - lmn) * h; },
      ticks: function () { var a = []; for (var i = 0; i <= 5; i++) { var t = lmn + (lmx - lmn) * i / 5; a.push(log ? Math.pow(10, t) : t); } return a; }
    };
  }

  function draw() {
    if (!DATA) return;
    var W = host.clientWidth || 700, H = 420, padL = 62, padR = 14, padT = 14, padB = 30, w = W - padL - padR, h = H - padT - padB;
    var sels = selected();
    statsEl.innerHTML = ""; corrEl.innerHTML = "";
    if (!sels.length) { host.innerHTML = '<p class="mon-empty">' + T("Отметьте валюты справа, чтобы построить график.", "Check currencies on the right to draw a chart.", "Marcá monedas a la derecha para trazar el gráfico.") + "</p>"; legEl.innerHTML = ""; if (noteEl) noteEl.textContent = ""; HOVER = null; hideTip(); return; }

    var svg = '<svg viewBox="0 0 ' + W + " " + H + '" width="100%" height="' + H + '" class="mon-svg">';
    var bn = baseName();

    // ----- СВЕЧИ -----
    if (type === "candle") {
      var slug = sels[0];
      var pts = rangeFilter(rebased(slug));
      var byDay = {};
      pts.forEach(function (p) { var d = p[0].slice(0, 10); (byDay[d] = byDay[d] || []).push(p[1]); });
      var days = Object.keys(byDay).sort();
      var ohlc = days.map(function (d) { var a = byDay[d]; return { d: d, o: a[0], c: a[a.length - 1], h: Math.max.apply(null, a), l: Math.min.apply(null, a) }; });
      if (!ohlc.length) { host.innerHTML = '<p class="mon-empty">' + T("Нет данных.", "No data.", "Sin datos.") + "</p>"; return; }
      var vs = []; ohlc.forEach(function (c) { vs.push(c.h, c.l); });
      var mn = Math.min.apply(null, vs), mx = Math.max.apply(null, vs); if (mn === mx) { mn *= 0.99; mx *= 1.01; }
      var sc = makeScale(mn, mx, logScale, padT, h);
      var cw = Math.max(2, Math.min(16, w / ohlc.length * 0.6));
      svg += grid(sc, W, padL, padR, fmtNum);
      ohlc.forEach(function (c, i) {
        var x = padL + (ohlc.length === 1 ? w / 2 : i / (ohlc.length - 1) * w);
        var up = c.c >= c.o, col = up ? "#33cc77" : "#dd5555";
        svg += '<line x1="' + x + '" y1="' + sc.Y(c.h) + '" x2="' + x + '" y2="' + sc.Y(c.l) + '" stroke="' + col + '" stroke-width="1"/>';
        var yo = sc.Y(c.o), yc = sc.Y(c.c), top = Math.min(yo, yc), bh = Math.max(1, Math.abs(yc - yo));
        svg += '<rect x="' + (x - cw / 2) + '" y="' + top + '" width="' + cw + '" height="' + bh + '" fill="' + col + '"/>';
      });
      svg += xlabels(ohlc.map(function (c) { return c.d; }), padL, w, H, padB);
      svg += "</svg>"; host.innerHTML = svg;
      legEl.innerHTML = '<span class="mon-lg"><i style="background:#33cc77"></i>' + esc(name(slug)) + " · " + T("свечи (день)", "candles (day)", "velas (día)") + "</span>";
      if (noteEl) noteEl.textContent = T("Свечи — по одной валюте (", "Candles — single currency (", "Velas — una sola moneda (") + name(slug) + T("), цена в ", "), price in ", "), precio en ") + bn + ". OHLC " + T("собран из точек дня.", "built from intraday points.", "armado con puntos del día.") + (sels.length > 1 ? T(" Отмечено несколько — показана первая.", " Several checked — first one shown.", " Varias marcadas — se muestra la primera.") : "") + (logScale ? T(" Лог-шкала.", " Log scale.", " Escala log.") : "");
      HOVER = { kind: "candle", W: W, padL: padL, w: w, dates: ohlc.map(function (c) { return c.d; }), Xi: function (i) { return padL + (ohlc.length === 1 ? w / 2 : i / (ohlc.length - 1) * w); }, ohlc: ohlc, name: name(slug), baseName: bn };
      mountHover(); renderStats(sels); return;
    }

    // ----- ПАРА A/B -----
    if (type === "ratio") {
      if (sels.length < 2) { host.innerHTML = '<p class="mon-empty">' + T("Отметьте минимум две валюты — покажем отношение A/B.", "Check at least two currencies — we plot the A/B ratio.", "Marcá al menos dos monedas — mostramos la relación A/B.") + "</p>"; legEl.innerHTML = ""; if (noteEl) noteEl.textContent = ""; HOVER = null; hideTip(); return; }
      var a = sels[0], b = sels[1];
      var rp = rangeFilter(ratioSeries(a, b));
      if (rp.length < 2) { host.innerHTML = '<p class="mon-empty">' + T("Нет пересечения дат для пары.", "No overlapping dates for the pair.", "Sin fechas en común para el par.") + "</p>"; return; }
      var rv = rp.map(function (p) { return p[1]; });
      var rmn = Math.min.apply(null, rv), rmx = Math.max.apply(null, rv); if (rmn === rmx) { rmn *= 0.99; rmx = rmx * 1.01 + 1e-9; }
      var rsc = makeScale(rmn, rmx, logScale, padT, h);
      var rx0 = dnum(rp[0][0]), rx1 = dnum(rp[rp.length - 1][0]), rxs = (rx1 - rx0) || 1;
      var RX = function (d) { return padL + (dnum(d) - rx0) / rxs * w; };
      svg += grid(rsc, W, padL, padR, fmtNum);
      var rd = ""; rp.forEach(function (p, k) { rd += (k ? "L" : "M") + RX(p[0]).toFixed(1) + "," + rsc.Y(p[1]).toFixed(1); });
      svg += '<path d="' + rd + '" fill="none" stroke="' + COLORS[0] + '" stroke-width="1.6"/>';
      svg += xlabels(rp.map(function (p) { return p[0]; }), padL, w, H, padB, RX);
      svg += "</svg>"; host.innerHTML = svg;
      var rlast = rp[rp.length - 1][1], rfirst = rp[0][1], rpc = (rlast / rfirst - 1) * 100;
      legEl.innerHTML = '<span class="mon-lg"><i style="background:' + COLORS[0] + '"></i>' + esc(ticker(a) || name(a)) + "/" + esc(ticker(b) || name(b)) +
        " <b>" + fmtNum(rlast) + "</b> <em class='mon-pc " + (rpc >= 0 ? "up" : "dn") + "'>" + fmtPct(rpc) + "</em></span>";
      if (noteEl) noteEl.textContent = T("Отношение ", "Ratio ", "Relación ") + name(a) + " / " + name(b) + T(" (сколько «B» за одну «A»). Первые две отмеченные валюты.", " (how much of B per one A). First two checked currencies.", " (cuánto B por cada A). Primeras dos monedas marcadas.") + (logScale ? T(" Лог-шкала.", " Log scale.", " Escala log.") : "");
      HOVER = { kind: "line", W: W, padL: padL, w: w, x0: rx0, xs: rxs, dates: rp.map(function (p) { return p[0]; }), dnums: rp.map(function (p) { return dnum(p[0]); }), Xd: RX, names: [ticker(a) + "/" + ticker(b)], cols: [COLORS[0]], maps: [(function () { var m = {}; rp.forEach(function (p) { m[p[0]] = p[1]; }); return m; })()], baseName: "" };
      mountHover(); return;
    }

    // ----- ЛИНИИ -----
    var single = sels.length === 1;
    var seriesData = sels.map(function (s) { return { s: s, pts: rangeFilter(rebased(s)) }; }).filter(function (o) { return o.pts.length; });
    if (!seriesData.length) { host.innerHTML = '<p class="mon-empty">' + T("Нет данных за период.", "No data for the period.", "Sin datos para el período.") + "</p>"; return; }
    seriesData.forEach(function (o) {
      var st = o.pts[0][1] || 1;
      o.norm = o.pts.map(function (p) { return [p[0], single ? p[1] : p[1] / st * 100]; });
    });
    var allv = [], allx = [];
    seriesData.forEach(function (o) { o.norm.forEach(function (p) { allv.push(p[1]); allx.push(dnum(p[0])); }); });
    var mn2 = Math.min.apply(null, allv), mx2 = Math.max.apply(null, allv); if (mn2 === mx2) { mn2 *= 0.99; mx2 = mx2 * 1.01 + 1; }
    var sc2 = makeScale(mn2, mx2, logScale, padT, h);
    var x0 = Math.min.apply(null, allx), x1 = Math.max.apply(null, allx), xs = (x1 - x0) || 1;
    function X(d) { return padL + (dnum(d) - x0) / xs * w; }
    svg += grid(sc2, W, padL, padR, single ? fmtNum : function (v) { return Math.round(v); });
    seriesData.forEach(function (o, i) {
      var col = COLORS[i % COLORS.length], d = "";
      o.norm.forEach(function (p, k) { d += (k ? "L" : "M") + X(p[0]).toFixed(1) + "," + sc2.Y(p[1]).toFixed(1); });
      svg += '<path d="' + d + '" fill="none" stroke="' + col + '" stroke-width="1.6"/>';
    });
    var allDates = seriesData[0].norm.map(function (p) { return p[0]; });
    svg += xlabels(allDates, padL, w, H, padB, X);
    svg += "</svg>"; host.innerHTML = svg;
    legEl.innerHTML = seriesData.map(function (o, i) {
      var last = o.norm[o.norm.length - 1][1], pc = pctChange(o.s);
      return '<span class="mon-lg"><i style="background:' + COLORS[i % COLORS.length] + '"></i>' + esc(name(o.s)) +
        " <b>" + (single ? fmtNum(last) + " " + bn : Math.round(last)) + "</b> " +
        (pc == null ? "" : "<em class='mon-pc " + (pc >= 0 ? "up" : "dn") + "'>" + fmtPct(pc) + "</em>") + "</span>";
    }).join("");
    if (noteEl) noteEl.textContent = (single
      ? T("Цена в ", "Price in ", "Precio en ") + bn + T(" (одна валюта — реальный курс).", " (single currency — real rate).", " (una moneda — tasa real).")
      : T("Индекс относительной динамики (старт = 100), база — ", "Relative index (start = 100), base — ", "Índice relativo (inicio = 100), base — ") + bn + T(". Так разномасштабные валюты сравнимы на одной шкале.", ". Lets currencies of different scale share one axis.", ". Así monedas de distinta escala comparten un eje.")) + (logScale ? T(" Лог-шкала.", " Log scale.", " Escala log.") : "");

    var uni = {}; seriesData.forEach(function (o) { o.pts.forEach(function (p) { uni[p[0]] = 1; }); });
    var udates = Object.keys(uni).sort();
    HOVER = {
      kind: "line", W: W, padL: padL, w: w, x0: x0, xs: xs, dates: udates, dnums: udates.map(dnum), Xd: function (d) { return X(d); },
      names: seriesData.map(function (o) { return name(o.s); }),
      cols: seriesData.map(function (o, i) { return COLORS[i % COLORS.length]; }),
      maps: seriesData.map(function (o) { var m = {}; o.pts.forEach(function (p) { m[p[0]] = p[1]; }); return m; }),
      baseName: bn
    };
    mountHover(); renderStats(sels); if (showCorr) renderCorr(sels);
  }

  // ---------- статистика по отмеченным (мин/макс/сред/волатильность за период) ----------
  function renderStats(sels) {
    var rows = sels.map(function (s) {
      var p = rangeFilter(rebased(s)).map(function (x) { return x[1]; });
      if (p.length < 2) return null;
      var mn = Math.min.apply(null, p), mx = Math.max.apply(null, p), avg = p.reduce(function (a, b) { return a + b; }, 0) / p.length;
      var rets = []; for (var i = 1; i < p.length; i++) { if (p[i - 1]) rets.push(p[i] / p[i - 1] - 1); }
      var vol = 0; if (rets.length) { var m = rets.reduce(function (a, b) { return a + b; }, 0) / rets.length; vol = Math.sqrt(rets.reduce(function (a, b) { return a + (b - m) * (b - m); }, 0) / rets.length) * 100; }
      return { s: s, mn: mn, mx: mx, avg: avg, vol: vol };
    }).filter(Boolean);
    if (!rows.length) { statsEl.innerHTML = ""; return; }
    var bn = baseName();
    statsEl.innerHTML = '<div class="mon-sub">' + T("Статистика за период", "Stats for the period", "Estadística del período") + " · " + esc(bn) + "</div>" +
      '<div class="mon-tbl-w"><table class="mon-tbl"><thead><tr><th>' + T("Валюта", "Currency", "Moneda") + "</th><th>min</th><th>max</th><th>" + T("средн.", "avg", "prom.") + "</th><th>" + T("волат.", "vol", "vol.") + "</th></tr></thead><tbody>" +
      rows.map(function (r) { return "<tr><td>" + esc(name(r.s)) + "</td><td>" + fmtNum(r.mn) + "</td><td>" + fmtNum(r.mx) + "</td><td>" + fmtNum(r.avg) + "</td><td>" + r.vol.toFixed(2) + "%</td></tr>"; }).join("") +
      "</tbody></table></div>";
  }

  // ---------- матрица корреляций (Пирсон по дневным доходностям) ----------
  function returnsMap(s) {
    var p = rangeFilter(rebased(s)), m = {};
    for (var i = 1; i < p.length; i++) { if (p[i - 1][1]) m[p[i][0]] = p[i][1] / p[i - 1][1] - 1; }
    return m;
  }
  function corr(ma, mb) {
    var xs = [], ys = [];
    for (var d in ma) { if (mb[d] != null) { xs.push(ma[d]); ys.push(mb[d]); } }
    var n = xs.length; if (n < 3) return null;
    var mx = xs.reduce(function (a, b) { return a + b; }, 0) / n, my = ys.reduce(function (a, b) { return a + b; }, 0) / n;
    var sxy = 0, sx = 0, sy = 0;
    for (var i = 0; i < n; i++) { var dx = xs[i] - mx, dy = ys[i] - my; sxy += dx * dy; sx += dx * dx; sy += dy * dy; }
    if (!sx || !sy) return null; return sxy / Math.sqrt(sx * sy);
  }
  function corrColor(c) {
    if (c == null) return "#1a1a1a";
    var t = Math.max(-1, Math.min(1, c));
    if (t >= 0) return "rgba(51," + Math.round(120 + 80 * t) + ",120," + (0.15 + 0.55 * t).toFixed(2) + ")";
    return "rgba(210,80,80," + (0.15 + 0.55 * (-t)).toFixed(2) + ")";
  }
  function renderCorr(sels) {
    if (sels.length < 2) { corrEl.innerHTML = ""; return; }
    var maps = sels.map(returnsMap);
    var head = "<tr><th></th>" + sels.map(function (s) { return "<th>" + esc(ticker(s) || name(s)) + "</th>"; }).join("") + "</tr>";
    var body = sels.map(function (s, i) {
      return "<tr><th>" + esc(ticker(s) || name(s)) + "</th>" + sels.map(function (t2, j) {
        var c = i === j ? 1 : corr(maps[i], maps[j]);
        return '<td style="background:' + corrColor(c) + '">' + (c == null ? "—" : c.toFixed(2)) + "</td>";
      }).join("") + "</tr>";
    }).join("");
    corrEl.innerHTML = '<div class="mon-sub">' + T("Корреляция дневных доходностей", "Correlation of daily returns", "Correlación de retornos diarios") + " · " + T("период", "period", "período") +
      '</div><div class="mon-tbl-w"><table class="mon-tbl mon-heat">' + head + body + "</table></div>" +
      '<p class="mon-note">' + T("1 — ходят синхронно, 0 — независимо, −1 — противоположно.", "1 — move together, 0 — independent, −1 — opposite.", "1 — se mueven juntos, 0 — independiente, −1 — opuesto.") + "</p>";
  }

  // ---------- экспорт ----------
  function download(dataUrl, fname) { var a = document.createElement("a"); a.href = dataUrl; a.download = fname; document.body.appendChild(a); a.click(); document.body.removeChild(a); }
  function exportCSV() {
    var sels = selected(); if (!sels.length) return;
    var uni = {}; var maps = sels.map(function (s) { var m = {}; rangeFilter(rebased(s)).forEach(function (p) { m[p[0]] = p[1]; uni[p[0]] = 1; }); return m; });
    var dates = Object.keys(uni).sort();
    var head = ["date"].concat(sels.map(function (s) { return (ticker(s) || name(s)).replace(/[;,]/g, " "); }));
    var lines = [head.join(";")];
    dates.forEach(function (d) { lines.push([d].concat(maps.map(function (m) { return m[d] == null ? "" : m[d]; })).join(";")); });
    download("data:text/csv;charset=utf-8," + encodeURIComponent("﻿" + lines.join("\n")), "ratescout-monitor.csv");
  }
  function exportPNG() {
    var svg = host.querySelector("svg"); if (!svg) return;
    var vb = svg.viewBox.baseVal, W = vb.width || host.clientWidth, H = vb.height || 420;
    var xml = new XMLSerializer().serializeToString(svg);
    var url = "data:image/svg+xml;base64," + btoa(unescape(encodeURIComponent(xml)));
    var img = new Image();
    img.onload = function () {
      var cv = document.createElement("canvas"); cv.width = W * 2; cv.height = H * 2;
      var ctx = cv.getContext("2d"); ctx.fillStyle = "#0c0c0c"; ctx.fillRect(0, 0, cv.width, cv.height);
      ctx.scale(2, 2); ctx.drawImage(img, 0, 0, W, H);
      try { download(cv.toDataURL("image/png"), "ratescout-monitor.png"); } catch (e) { if (noteEl) noteEl.textContent = T("Не удалось сохранить PNG.", "PNG export failed.", "No se pudo guardar el PNG."); }
    };
    img.onerror = function () { if (noteEl) noteEl.textContent = T("Не удалось сохранить PNG.", "PNG export failed.", "No se pudo guardar el PNG."); };
    img.src = url;
  }
  function copyLink() {
    writeURL();
    var url = location.href;
    var done = function () { if (linkBtn) { var old = linkBtn.textContent; linkBtn.textContent = T("скопировано ✓", "copied ✓", "copiado ✓"); setTimeout(function () { linkBtn.textContent = old; }, 1500); } };
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(url).then(done, done); else done();
  }

  function grid(sc, W, padL, padR, fmt) {
    var s = "";
    sc.ticks().forEach(function (v) {
      var y = sc.Y(v);
      s += '<line x1="' + padL + '" y1="' + y.toFixed(1) + '" x2="' + (W - padR) + '" y2="' + y.toFixed(1) + '" stroke="#2a2a2a"/>';
      s += '<text x="' + (padL - 6) + '" y="' + (y + 3).toFixed(1) + '" text-anchor="end" fill="#7fa" font-size="11">' + esc(fmt(v)) + "</text>";
    });
    return s;
  }
  function xlabels(dates, padL, w, H, padB, X) {
    if (!dates.length) return "";
    var idx = dates.length <= 1 ? [0] : [0, Math.floor((dates.length - 1) / 2), dates.length - 1];
    return idx.map(function (k) {
      var x = X ? X(dates[k]) : padL + (dates.length === 1 ? w / 2 : k / (dates.length - 1) * w);
      return '<text x="' + x.toFixed(1) + '" y="' + (H - padB + 16) + '" text-anchor="middle" fill="#888" font-size="11">' + fmtDate(dates[k]) + "</text>";
    }).join("");
  }

  // ---------- тултип ----------
  function mountHover() {
    if (!tipEl) {
      tipEl = document.createElement("div"); tipEl.className = "mon-tip"; tipEl.style.display = "none";
      crossEl = document.createElement("div"); crossEl.className = "mon-cross"; crossEl.style.display = "none";
    }
    host.appendChild(crossEl); host.appendChild(tipEl);
  }
  function hideTip() { if (tipEl) tipEl.style.display = "none"; if (crossEl) crossEl.style.display = "none"; }
  function onMove(e) {
    if (!HOVER) { hideTip(); return; }
    var svg = host.querySelector("svg"); if (!svg) { hideTip(); return; }
    var rect = svg.getBoundingClientRect();
    var scale = rect.width / HOVER.W;
    var vbX = (e.clientX - rect.left) / scale;
    if (HOVER.kind === "candle") {
      var n = HOVER.ohlc.length; if (!n) return;
      var i = n === 1 ? 0 : Math.round((vbX - HOVER.padL) / HOVER.w * (n - 1));
      i = Math.max(0, Math.min(n - 1, i));
      var c = HOVER.ohlc[i], cx = HOVER.Xi(i) * scale;
      var up = c.c >= c.o, col = up ? "#33cc77" : "#dd5555", bn = HOVER.baseName;
      showTip(cx, rect,
        '<div class="mon-tip-d">' + fmtDate(c.d) + "." + c.d.slice(0, 4) + '</div>' +
        '<div class="mon-tip-r"><span><i style="background:' + col + '"></i>' + esc(HOVER.name) + "</span></div>" +
        '<div class="mon-tip-o">O ' + fmtNum(c.o) + " · H " + fmtNum(c.h) + "<br>L " + fmtNum(c.l) + " · C " + fmtNum(c.c) + " " + esc(bn) + "</div>");
      return;
    }
    var ds = HOVER.dnums; if (!ds.length) return;
    var inv = HOVER.x0 + (vbX - HOVER.padL) / HOVER.w * HOVER.xs;
    var bi = 0, bd = Infinity;
    for (var k = 0; k < ds.length; k++) { var dd = Math.abs(ds[k] - inv); if (dd < bd) { bd = dd; bi = k; } }
    var date = HOVER.dates[bi], cx2 = HOVER.Xd(date) * scale;
    var rows = HOVER.names.map(function (nm, j) {
      var v = HOVER.maps[j][date];
      return '<div class="mon-tip-r"><span><i style="background:' + HOVER.cols[j] + '"></i>' + esc(nm) +
        "</span><b>" + (v == null ? "—" : fmtNum(v)) + "</b></div>";
    }).join("");
    showTip(cx2, rect,
      '<div class="mon-tip-d">' + fmtDate(date) + "." + date.slice(0, 4) + '</div>' + rows +
      (HOVER.baseName ? '<div class="mon-tip-u">' + esc(HOVER.baseName) + "</div>" : ""));
  }
  function showTip(cxPx, rect, html) {
    if (!tipEl) return;
    crossEl.style.display = "block"; crossEl.style.left = cxPx.toFixed(1) + "px";
    tipEl.innerHTML = html; tipEl.style.display = "block";
    var tw = tipEl.offsetWidth || 150;
    var left = cxPx + 14; if (left + tw > rect.width) left = cxPx - tw - 14; if (left < 2) left = 2;
    tipEl.style.left = left.toFixed(1) + "px";
  }
  host.addEventListener("mousemove", onMove);
  host.addEventListener("mouseleave", hideTip);

  window.addEventListener("resize", function () { if (DATA) draw(); });
})();
