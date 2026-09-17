#!/usr/bin/env python3
"""Еженедельный ИИ-отчёт по всем сайтам проекта в Telegram.

Без секретов и бесплатно: живые HTTP-проверки каждого сайта (главная, sitemap,
hreflang-связка) + статистика пайплайна (content_log.json, topics.json) +
рынок за неделю (history.json) + GSC-крохи (popular.json).

Секреты (опционально): OPENROUTER_API_KEY — ИИ-саммари и топ-3 действий;
TELEGRAM_TOKEN + ALERT_CHAT_ID — отправка (без них — печать в stdout).
"""
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

SITES = {
    # name: (homepage, sitemap) — EN живёт путём на RU-домене, sitemap общий корневой
    "RU": ("https://ratescout.ru", "https://ratescout.ru/sitemap.xml"),
    "ES": ("https://ratescout.oc.com.ar", "https://ratescout.oc.com.ar/sitemap.xml"),
    "EN": ("https://ratescout.ru/en", "https://ratescout.ru/sitemap.xml"),
    "FR": ("https://ratescout.info.gf", "https://ratescout.info.gf/sitemap.xml"),
}

REPORT_SYS = (
    "Ты — SEO-аналитик. Сожми технический отчёт по сети сайтов в дайджест для владельца "
    "(русский, до 1500 символов): 1) здоровье сайтов (что красное — первым), "
    "2) контент за неделю, 3) рынок одной строкой, 4) топ-3 конкретных действия на неделю. "
    "Без воды, без общих советов. Формат — короткие строки, эмодзи-маркеры."
)


def http_get(url, timeout=20):
    t0 = datetime.now(timezone.utc)
    try:
        with urllib.request.urlopen(urllib.request.Request(
                url, headers={"User-Agent": "RateScout-monitor/1.0"}), timeout=timeout) as r:
            body = r.read()
        ms = int((datetime.now(timezone.utc) - t0).total_seconds() * 1000)
        return r.status, body, ms
    except Exception as e:  # noqa: BLE001
        return 0, b"", -1


def check_site(name, base, sitemap_url):
    """(строки отчёта, ok_bool)."""
    lines, ok = [], True
    st, body, ms = http_get(base + "/")
    if st != 200:
        return [f"🔴 {name}: главная недоступна ({st or 'timeout'})"], False
    h = body.decode("utf-8", "ignore")
    langs = sorted(set(re.findall(r'hreflang="([a-z-]+)"', h)))
    xdom = "ratescout.oc.com.ar" in h and "ratescout.info.gf" in h
    lines.append(f"{'🟢' if ms < 1500 else '🟡'} {name}: {st}, {ms}мс, hreflang=[{','.join(langs)}]"
                 f"{'' if xdom else ' ⚠️нет кросс-домена'}")
    ok = ok and xdom
    st, body, _ = http_get(sitemap_url)
    n = body.decode("utf-8", "ignore").count("<loc>") if st == 200 else 0
    lines.append(f"   sitemap: {n} URL" if n else f"   🔴 sitemap битый ({st})")
    return lines, ok and bool(n)


def pipeline_stats():
    try:
        log = json.load(open(os.path.join(ROOT, "content_log.json"), encoding="utf-8"))
    except (OSError, ValueError):
        log = []
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    pub, skip, fail, live = {}, 0, 0, 0
    for e in log:
        if e.get("at", "") < week_ago:
            continue
        a = e.get("action", "")
        if a.startswith("market-") and not a.endswith(("skip", "live")):
            pub[e.get("lang", "?")] = pub.get(e.get("lang", "?"), 0) + 1
        elif a == "market-live":
            live += 1
        elif "skip" in a:
            skip += 1
        elif "selfcheck" in a and "FAIL" in e.get("verdict", ""):
            fail += 1
    try:
        topics = json.load(open(os.path.join(ROOT, "topics.json"), encoding="utf-8"))["topics"]
    except (OSError, ValueError, KeyError):
        topics = []
    tq = {}
    for t in topics:
        tq[t.get("status", "?")] = tq.get(t.get("status", "?"), 0) + 1
    return pub, skip, fail, live, tq


def main():
    L = [f"📊 RateScout — неделя до {datetime.now(timezone.utc):%Y-%m-%d}", ""]
    allok = True
    L.append("🌐 Сайты:")
    for name, (base, sm) in SITES.items():
        lines, ok = check_site(name, base, sm)
        allok = allok and ok
        L += lines
    try:
        from content_pipe import market_stats
        s, m, _ = market_stats(7)
        ups = ", ".join(f"{a} {b:+.0f}%" for a, b, _ in m[-2:][::-1]) or "—"
        dns = ", ".join(f"{a} {b:+.0f}%" for a, b, _ in m[:2]) or "—"
        L += ["", f"📈 Рынок 7д: рост {ups}; падение {dns}"]
    except Exception as e:  # noqa: BLE001
        L += ["", f"📈 Рынок: нет данных ({e})"]
    pub, skip, fail, live, tq = pipeline_stats()
    L += ["", f"✍️ Контент: посты {pub or '—'}; живые апдейты {live}; пропуски {skip}; fails {fail}",
          f"📚 Очередь тем: {tq or 'пусто'}"]
    try:
        pop = json.load(open(os.path.join(ROOT, "popular.json"), encoding="utf-8")).get("clicks", {})
        L += [f"🔎 GSC: направлений с кликами {len(pop)}, всего кликов {sum(pop.values())}"]
    except (OSError, ValueError):
        pass
    text = "\n".join(L)
    # ИИ-саммари (опционально)
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if key:
        try:
            from llm import chat
            digest = chat([{"role": "system", "content": REPORT_SYS},
                           {"role": "user", "content": text}], max_tokens=600)
            if digest:
                text = digest
        except Exception as e:  # noqa: BLE001
            text += f"\n\n(ИИ-саммари пропущено: {str(e)[:100]})"
    tok, chat_id = os.environ.get("TELEGRAM_TOKEN"), os.environ.get("ALERT_CHAT_ID")
    if not tok or not chat_id:
        print("TELEGRAM не настроен — отчёт:\n---\n" + text)
        return 0
    import urllib.parse
    for i in range(0, len(text), 3900):
        data = urllib.parse.urlencode({"chat_id": chat_id, "text": text[i:i + 3900],
                                       "disable_web_page_preview": "true"}).encode()
        try:
            with urllib.request.urlopen(urllib.request.Request(
                    f"https://api.telegram.org/bot{tok}/sendMessage", data=data, method="POST"),
                    timeout=30) as r:
                print("отчёт отправлен" if json.load(r).get("ok") else "ошибка Telegram")
        except Exception as e:  # noqa: BLE001
            print(f"ошибка отправки: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
