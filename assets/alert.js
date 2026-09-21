/* RateScout — страница оповещений о курсе пары A/B.
   Данные: /data/monitor.json (цена каждой валюты в USDT) → курс пары A/B = цена_A / цена_B.
   Подписка → deep-link в бота @RateScoutRUBot: start=A_B_<порог|p=точка>_<g|l>. */
(function () {
  var BOT = "RateScoutRUBot";
  var selA = document.getElementById("alertA"), selB = document.getElementById("alertB"),
      dirEl = document.getElementById("alertDir"), thrEl = document.getElementById("alertThr"),
      nowEl = document.getElementById("alertNow"), chartEl = document.getElementById("alertChart"),
      subBtn = document.getElementById("alertSub"), swap = document.getElementById("alertSwap");
  if (!selA || !selB) return;
  var LANG = (document.documentElement.getAttribute("lang") || "es").slice(0, 2);
  function T(r, e, s) { return LANG === "es" ? (s === undefined ? e : s) : (LANG === "en" ? e : r); }
  function LOC() { return LANG === "es" ? "es-AR" : (LANG === "en" ? "en-US" : "ru-RU"); }
  var CUR = {}, SER = {};

  function ticker(s) { var c = CUR[s]; return c && c.t ? c.t : s.toUpperCase(); }
  function nameOf(s) { var c = CUR[s]; return c ? (c.n + " (" + ticker(s) + ")") : s; }
  function priceOf(s) { var a = SER[s]; if (!a || !a.length) return null; var p = a[a.length - 1]; return p ? p[1] : null; }
  function fmt(v) {
    if (v == null || !isFinite(v)) return "—";
    var a = Math.abs(v);
    if (a >= 1000) return Math.round(v).toLocaleString(LOC());
    if (a >= 1) return "" + (+v.toFixed(4));
    if (a >= 0.0001) return "" + (+v.toFixed(8));
    return v.toPrecision(3);
  }
  // «плоское» число без разделителей — для поля порога и deep-link
  function trimNum(v) {
    var a = Math.abs(v);
    if (a >= 1000) return "" + Math.round(v);
    if (a >= 1) return "" + (+v.toFixed(4));
    if (a >= 0.0001) return "" + (+v.toFixed(8));
    return "" + (+v.toPrecision(4));
  }
  function parseThr() {
    var v = ("" + (thrEl.value || "")).replace(/\s/g, "");
    if (v.indexOf(".") < 0 && (v.match(/,/g) || []).length === 1) v = v.replace(",", ".");
    v = v.replace(/,/g, "");
    if (v === "" || isNaN(+v) || +v <= 0) return null;
    return +v;
  }
  // выровненный ряд курса пары A/B по общим датам
  function pairSeries(a, b) {
    var mb = {}; (SER[b] || []).forEach(function (p) { mb[p[0]] = p[1]; });
    var out = [];
    (SER[a] || []).forEach(function (p) { var vb = mb[p[0]]; if (vb && p[1] != null && vb != 0) out.push([p[0], p[1] / vb]); });
    return out;
  }
  function drawChart() {
    var pts = pairSeries(selA.value, selB.value);
    if (pts.length < 2) { chartEl.innerHTML = '<p class="mon-empty">' + T("Недостаточно данных для графика.", "Not enough data.", "Datos insuficientes para el gráfico.") + "</p>"; return; }
    var W = chartEl.clientWidth || 640, H = 260, padL = 60, padR = 12, padT = 12, padB = 26;
    var w = W - padL - padR, h = H - padT - padB;
    var vals = pts.map(function (p) { return p[1]; });
    var mn = Math.min.apply(null, vals), mx = Math.max.apply(null, vals); if (mx === mn) mx = mn + Math.abs(mn || 1) * 0.01 + 1;
    var thr = parseThr();
    if (thr != null) { mn = Math.min(mn, thr); mx = Math.max(mx, thr); }
    function X(i) { return padL + (pts.length === 1 ? w / 2 : i / (pts.length - 1) * w); }
    function Y(v) { return padT + h - (v - mn) / (mx - mn) * h; }
    var d = ""; pts.forEach(function (p, i) { d += (i ? "L" : "M") + X(i).toFixed(1) + " " + Y(p[1]).toFixed(1) + " "; });
    var grid = "", i;
    for (i = 0; i <= 4; i++) { var gv = mn + (mx - mn) * i / 4, gy = Y(gv).toFixed(1); grid += '<line x1="' + padL + '" y1="' + gy + '" x2="' + (W - padR) + '" y2="' + gy + '" stroke="rgba(255,255,255,.08)"/><text x="' + (padL - 6) + '" y="' + gy + '" fill="#8b909c" font-size="11" text-anchor="end" dominant-baseline="middle">' + fmt(gv) + "</text>"; }
    var thrLine = "";
    if (thr != null && thr >= mn && thr <= mx) { var yy = Y(thr).toFixed(1); thrLine = '<line x1="' + padL + '" y1="' + yy + '" x2="' + (W - padR) + '" y2="' + yy + '" stroke="#c9a558" stroke-dasharray="5 3" stroke-width="1.5"/><text x="' + (W - padR) + '" y="' + (yy - 4) + '" fill="#c9a558" font-size="11" text-anchor="end">' + T("порог", "target", "umbral") + " " + fmt(thr) + "</text>"; }
    var labels = "";
    [0, Math.floor((pts.length - 1) / 2), pts.length - 1].forEach(function (ix) { labels += '<text x="' + X(ix).toFixed(1) + '" y="' + (H - padB + 14) + '" fill="#8b909c" font-size="11" text-anchor="middle">' + ("" + pts[ix][0]).slice(5, 10) + "</text>"; });
    chartEl.innerHTML = '<svg viewBox="0 0 ' + W + " " + H + '" width="100%" height="' + H + '" class="mon-svg">' + grid + thrLine + '<path d="' + d + '" fill="none" stroke="#4ea1ff" stroke-width="2"/>' + labels + "</svg>";
  }
  function refresh() {
    var a = selA.value, b = selB.value, pa = priceOf(a), pb = priceOf(b);
    if (a === b) { nowEl.innerHTML = T("Выберите разные валюты.", "Pick two different currencies.", "Elegí distintas monedas."); }
    else if (pa != null && pb != null && pb != 0) {
      var rate = pa / pb;
      nowEl.innerHTML = T("Сейчас", "Now", "Ahora") + ": <b>1 " + ticker(a) + " = " + fmt(rate) + " " + ticker(b) + "</b>";
      if (!thrEl.value) thrEl.value = trimNum(rate);
    } else { nowEl.textContent = "—"; }
    drawChart();
  }
  function subscribe() {
    var a = selA.value, b = selB.value, thr = parseThr(), dir = dirEl.value;
    if (a === b) { alert(T("Выберите две разные валюты.", "Pick two different currencies.", "Elegí dos monedas distintas.")); return; }
    if (thr == null) { alert(T("Введите порог — число больше 0.", "Enter a threshold — number > 0.", "Ingresá un umbral — número mayor que 0.")); return; }
    var enc = a + "_" + b + "_" + ("" + thr).replace(".", "p") + "_" + dir;
    if (enc.length > 64) { alert(T("Слишком длинно — выберите валюты с короткими кодами.", "Too long — pick shorter-coded currencies.", "Demasiado largo — elegí monedas con códigos cortos.")); return; }
    window.open("https://t.me/" + BOT + "?start=" + enc, "_blank", "noopener");
  }

  fetch("/data/monitor.json").then(function (r) { return r.json(); }).then(function (j) {
    CUR = j.cur || {}; SER = j.series || {};
    var slugs = Object.keys(SER).filter(function (s) { return (SER[s] || []).length; }).sort(function (x, y) { return nameOf(x).localeCompare(nameOf(y)); });
    var opts = slugs.map(function (s) { return '<option value="' + s + '">' + nameOf(s) + "</option>"; }).join("");
    selA.innerHTML = opts; selB.innerHTML = opts;
    var q = new URLSearchParams(location.search);
    var a = q.get("a"), b = q.get("b");
    selA.value = (a && SER[a]) ? a : (SER.bitcoin ? "bitcoin" : slugs[0]);
    var defB = SER.ethereum && "ethereum" !== selA.value ? "ethereum" : null;
    if (!defB) { for (var k = 0; k < slugs.length; k++) { if (slugs[k] !== selA.value) { defB = slugs[k]; break; } } }
    selB.value = (b && SER[b] && b !== selA.value) ? b : defB;
    if (q.get("thr")) thrEl.value = q.get("thr");
    if (q.get("dir") === "l" || q.get("dir") === "g") dirEl.value = q.get("dir");
    refresh();
  }).catch(function () { if (nowEl) nowEl.textContent = T("Не удалось загрузить курсы.", "Failed to load rates.", "No se pudieron cargar las tasas."); });

  selA.addEventListener("change", refresh);
  selB.addEventListener("change", refresh);
  dirEl.addEventListener("change", drawChart);
  thrEl.addEventListener("input", drawChart);
  swap.addEventListener("click", function () { var t = selA.value; selA.value = selB.value; selB.value = t; thrEl.value = ""; refresh(); });
  subBtn.addEventListener("click", subscribe);
  window.addEventListener("resize", drawChart);
})();
