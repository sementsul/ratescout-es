#!/usr/bin/env python3
"""SVG-графики для Blogger-постов — только stdlib, без Pillow.

Нормированные линии (% от первой точки окна) для 3 активов + min/max-подписи.
Возвращает SVG-строку 640×280 — вставляется в пост как есть (Blogger ест inline SVG).
"""
import html


COLORS = ["#6e6eff", "#e67e22", "#0a8a0a"]


def svg_chart(series, title="", width=640, height=280):
    """series: [(label, [values])]. Пустые/короткие ряды пропускаются."""
    rows = [(lb, [v for v in vals if isinstance(v, (int, float)) and v])
            for lb, vals in series]
    rows = [(lb, v) for lb, v in rows if len(v) >= 2 and v[0]]
    if not rows:
        return ""
    W, H, PL, PR, PT, PB = width, height, 46, 12, 26, 22
    iw, ih = W - PL - PR, H - PT - PB
    out = [f"<svg xmlns='http://www.w3.org/2000/svg' width='{W}' height='{H}' "
           f"viewBox='0 0 {W} {H}' style='max-width:100%;background:#ffffff;"
           f"border:1px solid #dddddd;font-family:sans-serif'>"]
    if title:
        out.append(f"<text x='{W // 2}' y='17' text-anchor='middle' font-size='14' "
                   f"font-weight='bold' fill='#222222'>{html.escape(title)}</text>")
    # общая шкала % по всем рядам
    allpct = []
    normed = []
    for lb, v in rows:
        base = v[0]
        pct = [(x - base) / base * 100 for x in v]
        normed.append((lb, pct))
        allpct += pct
    lo, hi = min(allpct), max(allpct)
    if hi == lo:
        hi = lo + 1
    # сетка 4 линии
    for g in range(5):
        y = PT + ih - (g / 4) * ih
        val = lo + (hi - lo) * g / 4
        out.append(f"<line x1='{PL}' y1='{y:.0f}' x2='{W - PR}' y2='{y:.0f}' "
                   f"stroke='#eeeeee'/>")
        out.append(f"<text x='{PL - 5}' y='{y + 4:.0f}' text-anchor='end' font-size='10' "
                   f"fill='#777777'>{val:+.1f}%</text>")
    n = max(len(p) for _, p in normed)
    for idx, (lb, pct) in enumerate(normed):
        col = COLORS[idx % len(COLORS)]
        pts = " ".join(f"{PL + i / (n - 1) * iw:.1f},{PT + ih - (v - lo) / (hi - lo) * ih:.1f}"
                       for i, v in enumerate(pct))
        out.append(f"<polyline points='{pts}' fill='none' stroke='{col}' stroke-width='2'/>")
        lx, ly = PL + (len(pct) - 1) / (n - 1) * iw, PT + ih - (pct[-1] - lo) / (hi - lo) * ih
        out.append(f"<circle cx='{lx:.1f}' cy='{ly:.1f}' r='3' fill='{col}'/>")
        out.append(f"<text x='{W - PR}' y='{ly + 4:.1f}' font-size='11' font-weight='bold' "
                   f"fill='{col}'>{html.escape(lb)} {pct[-1]:+.1f}%</text>")
    out.append("</svg>")
    return "".join(out)
