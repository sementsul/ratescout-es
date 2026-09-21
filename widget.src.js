/* RateScout embeddable widget — self-contained, no deps. {{BASE}} подставляется при сборке.
   Режимы:
     • курс по популярной паре:   data-pair="usdt-rub"        (лёгкий, widget-data.json)
     • курс по ЛЮБОЙ паре:        data-from="bitcoin" data-to="sberbank"
     • мини-конвертер (любые пары): data-widget="converter"
   Полную карту курсов (widget-rates.json) грузим только когда нужна произвольная пара/конвертер. */
(function () {
  var BASE = "{{BASE}}";
  var SMALL = null, FULL = null;
  function el(tag, style, html) {
    var e = document.createElement(tag);
    if (style) e.setAttribute("style", style);
    if (html != null) e.innerHTML = html;
    return e;
  }
  var CARD = "font:13px/1.4 system-ui,Arial,sans-serif;display:inline-block;border:1px solid #d0d5dd;border-radius:8px;padding:10px 14px;background:#fff;color:#111;min-width:210px";
  var LBL = "font-size:11px;color:#667085;text-transform:uppercase;letter-spacing:.04em";
  var BIG = "font-size:20px;font-weight:700;margin:2px 0";
  var LINK = "color:#0a66c2;text-decoration:none;font-weight:600";
  var ATTR = "display:block;margin-top:6px;font-size:11px;color:#98a2b3;text-decoration:none";
  var INP = "width:100%;box-sizing:border-box;padding:6px 8px;margin:4px 0;border:1px solid #d0d5dd;border-radius:6px;font:inherit;color:#111;background:#fff";
  var OPEN = "{{OPEN}}";
  var CRED = "{{CRED}}";
  var NODATA = "{{NODATA}}";

  function num(v) { v = parseFloat(String(v).replace(/\s/g, "")); return isNaN(v) ? 0 : v; }
  function fmt(v) {
    if (v >= 1000) return v.toLocaleString("{{LOCALE}}", { maximumFractionDigits: 0 });
    if (v >= 1) return v.toLocaleString("{{LOCALE}}", { maximumFractionDigits: 2 });
    return v.toFixed(6).replace(/0+$/, "").replace(/\.$/, "");
  }
  function rateBox(fromT, toT, rateStr, url) {
    return '<div style="' + CARD + '"><div style="' + LBL + '">' + fromT + ' → ' + toT + '</div>' +
      '<div style="' + BIG + '">1 ' + fromT + ' = ' + rateStr + ' ' + toT + '</div>' +
      '<a href="' + url + '" target="_blank" rel="noopener" style="' + LINK + '">' + OPEN + '</a>' +
      '<a href="' + BASE + '/" target="_blank" rel="noopener" style="' + ATTR + '">' + CRED + '</a></div>';
  }

  function renderRate(box) {                       // популярная пара из widget-data.json
    var k = (box.getAttribute("data-pair") || "usdt-rub").toLowerCase();
    var p = SMALL && SMALL.pairs[k]; if (!p) return;
    box.innerHTML = rateBox(p.from, p.to, p.rate, p.url);
  }
  function renderCustom(box) {                     // произвольная пара из widget-rates.json
    var f = box.getAttribute("data-from"), t = box.getAttribute("data-to");
    if (!FULL) return;
    var cf = FULL.cur[f] || { t: f }, ct = FULL.cur[t] || { t: t };
    var r = FULL.rates[f] && FULL.rates[f][t];
    if (!r) { box.innerHTML = rateBox(cf.t, ct.t, "—", BASE + "/valuta/" + f + "/"); return; }
    box.innerHTML = rateBox(cf.t, ct.t, fmt(num(r)), BASE + "/valuta/" + f + "/");
  }
  function renderConv(box) {                        // конвертер по ЛЮБЫМ парам
    if (!FULL) return;
    var slugs = Object.keys(FULL.cur).sort(function (a, b) { return FULL.cur[a].n.localeCompare(FULL.cur[b].n); });
    var card = el("div", CARD);
    card.appendChild(el("div", LBL, "{{CONV}}"));
    var amt = el("input", INP); amt.type = "number"; amt.min = "0"; amt.step = "any"; amt.value = "1";
    function mkSel(def) {
      var s = el("select", INP);
      slugs.forEach(function (k) { var o = el("option", null, FULL.cur[k].n + " (" + FULL.cur[k].t + ")"); o.value = k; s.appendChild(o); });
      if (FULL.cur[def]) s.value = def;
      return s;
    }
    var fromS = mkSel(box.getAttribute("data-from") || "bitcoin");
    var toS = mkSel(box.getAttribute("data-to") || "sberbank");
    var out = el("div", BIG);
    var go = el("a", LINK, OPEN); go.target = "_blank"; go.rel = "noopener";
    var attr = el("a", ATTR, CRED); attr.href = BASE + "/"; attr.target = "_blank"; attr.rel = "noopener";
    function calc() {
      var f = fromS.value, t = toS.value, r = FULL.rates[f] && FULL.rates[f][t];
      if (!r) { out.textContent = NODATA; go.style.display = "none"; return; }
      out.innerHTML = fmt(num(amt.value) * num(r)) + " " + FULL.cur[t].t;
      go.href = BASE + "/valuta/" + f + "/"; go.style.display = "";
    }
    amt.addEventListener("input", calc); fromS.addEventListener("change", calc); toS.addEventListener("change", calc);
    card.appendChild(amt); card.appendChild(fromS); card.appendChild(toS);
    card.appendChild(out); card.appendChild(go); card.appendChild(attr);
    box.innerHTML = ""; box.appendChild(card); calc();
  }

  function isCustom(b) {
    return b.getAttribute("data-widget") === "converter" || (b.getAttribute("data-from") && b.getAttribute("data-to"));
  }
  function renderOne(b) {
    if (b.getAttribute("data-widget") === "converter") renderConv(b);
    else if (b.getAttribute("data-from") && b.getAttribute("data-to")) renderCustom(b);
    else renderRate(b);
  }
  function init() {
    var els = document.querySelectorAll(".ratescout-widget,#ratescout-widget,[data-ratescout-widget]");
    if (!els.length) return;
    var arr = Array.prototype.slice.call(els);
    var jobs = [];
    if (arr.some(function (b) { return !isCustom(b); }) && !SMALL)
      jobs.push(fetch(BASE + "/widget-data.json").then(function (r) { return r.json(); }).then(function (d) { SMALL = d; }));
    if (arr.some(isCustom) && !FULL)
      jobs.push(fetch(BASE + "/widget-rates.json").then(function (r) { return r.json(); }).then(function (d) { FULL = d; }));
    Promise.all(jobs).then(function () { arr.forEach(renderOne); }).catch(function () {});
  }
  window.RateScoutWidget = { refresh: init };
  if (document.readyState !== "loading") init();
  else document.addEventListener("DOMContentLoaded", init);
})();
