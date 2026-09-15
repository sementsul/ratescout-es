#!/usr/bin/env python3
"""Автопостинг дневного дайджеста в Blogger (Google Blogger API v3) — RU/ES/EN/FR.

Язык выбирается переменной BLOGGER_LANG (ru|es|en|fr, по умолчанию ru — старое поведение).
Под каждый язык — свой блог и свой вечный пост (PATCH на месте, без плодящихся статей):

  Общие OAuth-секреты (один Google-аккаунт — владелец всех блогов):
    BLOGGER_CLIENT_ID, BLOGGER_CLIENT_SECRET, BLOGGER_REFRESH_TOKEN
  На язык XX (XX = RU|ES|EN|FR, для RU годятся и короткие имена без суффикса):
    BLOGGER_XX_BLOG_ID  — числовой id блога (из Atom-ленты: tag:blogger.com,1999:blog-<ID>)
    BLOGGER_XX_POST_ID  — (опц.) id вечного поста; пусто на первом запуске → скрипт
                          создаст пост и напечатает id для этого секрета
    BLOGGER_XX_TITLE    — (опц.) заголовок вечного поста
    BLOGGER_XX_SRC      — (опц.) URL daily-JSON-источника

Источники daily-JSON по умолчанию:
  ru → https://ratescout.ru/daily.json        (основной сайт)
  es → https://ratescout.oc.com.ar/daily-es.json
  en → https://ratescout.oc.com.ar/daily-en.json
  fr → https://ratescout.oc.com.ar/daily-fr.json

Ссылки на валюты ([тикер] → страница /valuta/<слаг>/) берутся из поля "coins"
daily-JSON и ведут на языковую версию сайта (site+prefix из таблицы LANGS).
Без секретов — сухой прогон (печатает заголовок и пример таблицы, не публикует).
"""
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request

LANG = (os.environ.get("BLOGGER_LANG") or "ru").lower()

LANGS = {
    # site — языковая версия сайта для ссылок на валюты; prefix — префикс языка в путях.
    "ru": {"src": "https://ratescout.ru/daily.json",
           "title": "Курсы криптовалют сегодня — сводка RateScout",
           "site": "https://ratescout.ru", "prefix": "",
           "img_alt": "Крипторынок за сутки",
           "th": ("Валюта", "Цена, USDT", "Изм. 24ч", "Обменников")},
    "es": {"src": "https://ratescout.oc.com.ar/daily-es.json",
           "title": "Criptomonedas hoy — resumen RateScout",
           "site": "https://ratescout.oc.com.ar", "prefix": "",
           "img_alt": "Criptomercado en 24h",
           "th": ("Moneda", "Precio, USDT", "Var. 24h", "Cambistas")},
    "en": {"src": "https://ratescout.oc.com.ar/daily-en.json",
           "title": "Crypto rates today — RateScout digest",
           "site": "https://ratescout.ru", "prefix": "/en",
           "img_alt": "Crypto market · 24h",
           "th": ("Currency", "Price, USDT", "24h chg.", "Exchangers")},
    "fr": {"src": "https://ratescout.oc.com.ar/daily-fr.json",
           "title": "Taux crypto du jour — résumé RateScout",
           "site": "https://ratescout.info.gf", "prefix": "",
           "img_alt": "Marché crypto · 24h",
           "th": ("Monnaie", "Prix, USDT", "Var. 24h", "Changeurs")},
}
if LANG not in LANGS:
    print(f"неизвестный BLOGGER_LANG={LANG} (ru|es|en|fr)")
    sys.exit(1)
CFG = LANGS[LANG]
SFX = "_" + LANG.upper()


def _env(*names):
    for n in names:
        v = os.environ.get(n)
        if v:
            return v
    return ""


CID = os.environ.get("BLOGGER_CLIENT_ID")
CSEC = os.environ.get("BLOGGER_CLIENT_SECRET")
RTOK = os.environ.get("BLOGGER_REFRESH_TOKEN")
# Суффиксные имена приоритетны; короткие (без суффикса) — для RU, как раньше.
BLOG = _env("BLOGGER" + SFX + "_BLOG_ID", "BLOGGER_BLOG_ID") if LANG != "ru" \
    else _env("BLOGGER_RU_BLOG_ID", "BLOGGER_BLOG_ID")
# ID вечного поста: секрет приоритетен; иначе — файл blogger_posted.json в корне репо
# (скрипт сам дописывает туда id после первого создания, workflow коммитит файл обратно).
POSTED_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "blogger_posted.json")


def _posted_id():
    try:
        return json.load(open(POSTED_FILE, encoding="utf-8")).get(LANG, "")
    except (OSError, ValueError):
        return ""


def _save_posted_id(pid):
    try:
        cur = json.load(open(POSTED_FILE, encoding="utf-8"))
    except (OSError, ValueError):
        cur = {}
    cur[LANG] = pid
    json.dump(cur, open(POSTED_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[{LANG}] id сохранён в blogger_posted.json (workflow закоммитит файл)")


PID = _env("BLOGGER" + SFX + "_POST_ID", "BLOGGER_POST_ID") if LANG != "ru" \
    else _env("BLOGGER_RU_POST_ID", "BLOGGER_POST_ID")
if not PID:
    PID = _posted_id()
SRC = _env("BLOGGER" + SFX + "_SRC", "DAILY_JSON_URL") or CFG["src"]
STABLE_TITLE = _env("BLOGGER" + SFX + "_TITLE", "BLOGGER_POST_TITLE") or CFG["title"]


def access_token():
    data = urllib.parse.urlencode({"client_id": CID, "client_secret": CSEC,
                                   "refresh_token": RTOK, "grant_type": "refresh_token"}).encode()
    with urllib.request.urlopen(urllib.request.Request("https://oauth2.googleapis.com/token",
                                                       data=data, method="POST"), timeout=30) as r:
        return json.load(r)["access_token"]


def _linkify(text):
    # обычные URL → кликабельные <a> (в HTML Blogger автолинка нет)
    return re.sub(r'(https?://[^\s<]+)', r'<a href="\1">\1</a>', text)


def _change_color(chg):
    c = (chg or "").strip()
    if c.startswith("+"):
        return "#0a8a0a"   # рост — зелёный
    if c.startswith("-"):
        return "#c0392b"   # падение — красный
    return "#555"          # без изменения — серый


def _coin_href(slug):
    return f"{CFG['site']}{CFG['prefix']}/valuta/{slug}/"


def render_coins_table(coins):
    """Таблица «все валюты» из структурного списка coins (со слагами):
    тикер — ссылкой на страницу валюты на языке поста. Стили инлайновые."""
    if not coins:
        return ""
    t0, t1, t2, t3 = (html.escape(x) for x in CFG["th"])
    rows = []
    for i, c in enumerate(coins):
        bg = "#ffffff" if i % 2 == 0 else "#f7f7f7"
        tick = html.escape(c.get("ticker", "?"))
        href = _coin_href(c["slug"]) if c.get("slug") else ""
        cell0 = (f'<a href="{href}">{tick}</a>' if href else tick)
        rows.append(
            f'<tr style="background:{bg}">'
            f'<td style="padding:6px 10px;font-weight:600;white-space:nowrap">{cell0}</td>'
            f'<td style="padding:6px 10px;text-align:right;white-space:nowrap">'
            f'{html.escape(str(c.get("price", "—")))}</td>'
            f'<td style="padding:6px 10px;text-align:right;white-space:nowrap;'
            f'color:{_change_color(str(c.get("chg", "")))}">{html.escape(str(c.get("chg", "—")))}</td>'
            f'<td style="padding:6px 10px;text-align:right;white-space:nowrap;color:#777">'
            f'{html.escape(str(c.get("liq", "")))}</td>'
            f'</tr>')
    thead = ('<tr style="background:#eeeeee">'
             f'<th style="padding:8px 10px;text-align:left;color:#222222;border-bottom:2px solid #cccccc">{t0}</th>'
             f'<th style="padding:8px 10px;text-align:right;color:#222222;border-bottom:2px solid #cccccc">{t1}</th>'
             f'<th style="padding:8px 10px;text-align:right;color:#222222;border-bottom:2px solid #cccccc">{t2}</th>'
             f'<th style="padding:8px 10px;text-align:right;color:#222222;border-bottom:2px solid #cccccc">{t3}</th>'
             '</tr>')
    return ('<div style="overflow-x:auto">'
            '<table style="border-collapse:collapse;width:100%;font-size:14px;'
            'color:#222222;background:#ffffff;border:1px solid #dddddd">'
            f'<thead>{thead}</thead><tbody>{"".join(rows)}</tbody></table></div>')


def render_full_list_table(fl):
    """Старый формат: строки 'ТИКЕР: цена · изм% · обменников' → HTML-таблица (без ссылок).
    Используется, когда в daily-JSON нет поля coins (обратная совместимость)."""
    heading = {"ru": "Все валюты — цена USDT · изм. 24ч · обменников",
               "es": "Todas las monedas — precio USDT · var. 24h · cambistas",
               "en": "All currencies — price USDT · 24h · exchangers",
               "fr": "Toutes les monnaies — prix USDT · var. 24h · changeurs"}[LANG]
    rows = []
    for ln in fl.split("\n"):
        s = ln.strip()
        if not s:
            continue
        if s.startswith("📋"):                       # строка-заголовок с количеством
            heading = s.lstrip("📋").strip().rstrip(":")
            continue
        if ": " not in s:
            continue
        tick, rest = s.split(": ", 1)
        cells = [p.strip() for p in rest.split(" · ")]
        if len(cells) != 3:                          # не наш формат — пропускаем
            continue
        price, chg, exch = cells
        bg = "#ffffff" if len(rows) % 2 == 0 else "#f7f7f7"
        rows.append(
            f'<tr style="background:{bg}">'
            f'<td style="padding:6px 10px;font-weight:600;white-space:nowrap">{html.escape(tick)}</td>'
            f'<td style="padding:6px 10px;text-align:right;white-space:nowrap">{html.escape(price)}</td>'
            f'<td style="padding:6px 10px;text-align:right;white-space:nowrap;color:{_change_color(chg)}">{html.escape(chg)}</td>'
            f'<td style="padding:6px 10px;text-align:right;white-space:nowrap;color:#777">{html.escape(exch)}</td>'
            f'</tr>')
    if not rows:
        return ""
    t0, t1, t2, t3 = (html.escape(x) for x in CFG["th"])
    thead = ('<tr style="background:#eeeeee">'
             f'<th style="padding:8px 10px;text-align:left;color:#222222;border-bottom:2px solid #cccccc">{t0}</th>'
             f'<th style="padding:8px 10px;text-align:right;color:#222222;border-bottom:2px solid #cccccc">{t1}</th>'
             f'<th style="padding:8px 10px;text-align:right;color:#222222;border-bottom:2px solid #cccccc">{t2}</th>'
             f'<th style="padding:8px 10px;text-align:right;color:#222222;border-bottom:2px solid #cccccc">{t3}</th>'
             '</tr>')
    return (f'<h3>{html.escape(heading)}</h3>'
            '<div style="overflow-x:auto">'
            '<table style="border-collapse:collapse;width:100%;font-size:14px;'
            'color:#222222;background:#ffffff;border:1px solid #dddddd">'
            f'<thead>{thead}</thead><tbody>{"".join(rows)}</tbody></table></div>')


def build_html(d):
    cap = _linkify(html.escape(d.get("caption", "")).replace("\n", "<br>"))
    img = (f'<p><img src="{html.escape(d["image"])}" alt="{html.escape(CFG["img_alt"])}" /></p>'
           if d.get("image") else "")
    parts = [img, f"<p>{cap}</p>"]
    if d.get("coins"):
        parts.append(render_coins_table(d["coins"]))
    elif d.get("full_list"):
        parts.append(render_full_list_table(d["full_list"]))
    return "".join(parts)


def main():
    try:
        with urllib.request.urlopen(SRC, timeout=30) as r:
            d = json.load(r)
    except Exception as e:                       # noqa: BLE001
        print(f"не удалось получить {SRC}: {e}")
        return 0
    if not d.get("has_data"):
        print("нет данных за сутки — публикация пропущена")
        return 0
    if not all([CID, CSEC, RTOK, BLOG]):
        print(f"Blogger-секреты не заданы (lang={LANG}) — сухой прогон.\n--- заголовок ---")
        print(STABLE_TITLE)
        print(f"--- источник: {SRC} · валют в coins: {len(d.get('coins') or [])} ---")
        return 0
    body = json.dumps({"kind": "blogger#post", "title": STABLE_TITLE,
                       "content": build_html(d)}).encode()
    token = access_token()
    if PID:
        # ОБНОВЛЯЕМ существующий пост (один вечный URL, свежий контент)
        url = f"https://www.googleapis.com/blogger/v3/blogs/{BLOG}/posts/{PID}"
        method, action = "PATCH", "обновлён"
    else:
        # Первый раз: создаём пост и печатаем его id для секрета BLOGGER_<LANG>_POST_ID
        url = f"https://www.googleapis.com/blogger/v3/blogs/{BLOG}/posts/"
        method, action = "POST", "создан"
    req = urllib.request.Request(url, data=body, method=method,
                                 headers={"Authorization": f"Bearer {token}",
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            res = json.load(r)
        print(f"[{LANG}] пост {action}:", res.get("url"))
        if not PID:
            _save_posted_id(res.get("id"))
            print(f"⚠ Запасной вариант: положи этот id в GitHub-секрет BLOGGER_{LANG.upper()}_POST_ID — "
                  f"тогда файл не нужен.\nBLOGGER_{LANG.upper()}_POST_ID = {res.get('id')}")
        return 0
    except Exception as e:                        # noqa: BLE001
        print(f"ошибка публикации в Blogger: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
