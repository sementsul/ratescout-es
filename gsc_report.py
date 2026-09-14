#!/usr/bin/env python3
"""Еженедельный отчёт из Google Search Console в Telegram (владельцу в личку).

Показывает за последнюю ОСЕВШУЮ неделю (у GSC задержка данных ~2-3 дня):
  • клики / показы / CTR / средняя позиция + динамика к предыдущей неделе;
  • топ-10 запросов по показам;
  • топ-10 страниц по кликам;
  • «дожать» — запросы со средней позицией 8–20 и заметными показами (2-я страница выдачи):
    именно они подсказывают, какие направления/страницы стоит усилить.

Секреты — ТОЛЬКО из окружения (GitHub Secrets), в коде их нет:
  GSC_SA_JSON      — JSON-ключ сервис-аккаунта Google (у него должен быть доступ к ресурсу в Search Console)
  GSC_SITE         — ресурс: 'sc-domain:ratescout.ru' (домен-ресурс) или 'https://ratescout.ru/' (URL-префикс)
  TELEGRAM_TOKEN   — тот же бот, что у каналов
  ALERT_CHAT_ID    — id личного чата владельца с ботом (как у сторожа)
Без секретов — сухой прогон (печатает, что сделал бы, ничего не шлёт).
"""
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))


def _default_site():
    if os.environ.get("GSC_SITE"):
        return os.environ["GSC_SITE"]
    try:
        d = json.load(open(os.path.join(ROOT, "data.json"), encoding="utf-8"))["site"]["domain"]
        return f"sc-domain:{d}"
    except (OSError, ValueError, KeyError):
        return "sc-domain:ratescout.ru"


SITE = _default_site()
try:
    _CUR = json.load(open(os.path.join(ROOT, "currencies.json"), encoding="utf-8"))["currencies"]
except (OSError, ValueError):
    _CUR = {}
API = "https://www.googleapis.com/webmasters/v3/sites/{site}/searchAnalytics/query"
SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
LAG_DAYS = 3          # данные GSC отстают на ~2-3 дня — берём осевшее окно
WINDOW = 7            # длина окна отчёта, дней


def _access_token(sa_json):
    """Access-token сервис-аккаунта Google (google-auth ставится в CI)."""
    from google.oauth2 import service_account
    import google.auth.transport.requests
    creds = service_account.Credentials.from_service_account_info(
        json.loads(sa_json), scopes=[SCOPE])
    creds.refresh(google.auth.transport.requests.Request())
    return creds.token


def _query(token, start, end, dimensions, limit=25):
    body = json.dumps({"startDate": start, "endDate": end,
                       "dimensions": dimensions, "rowLimit": limit}).encode()
    url = API.format(site=urllib.parse.quote(SITE, safe=""))
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"Authorization": f"Bearer {token}",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r).get("rows", [])


def _totals(rows):
    c = sum(x["clicks"] for x in rows)
    i = sum(x["impressions"] for x in rows)
    return c, i


def _pct(cur, prev):
    if not prev:
        return "—"
    d = (cur - prev) / prev * 100
    return f"{d:+.0f}%"


def _short_url(u):
    return u.replace("https://ratescout.ru", "").replace("https://ratescout.ru/", "/") or "/"


def build_report(token):
    today = datetime.now(timezone.utc).date()
    end = today - timedelta(days=LAG_DAYS)
    start = end - timedelta(days=WINDOW - 1)
    pend = start - timedelta(days=1)
    pstart = pend - timedelta(days=WINDOW - 1)
    s, e = start.isoformat(), end.isoformat()
    ps, pe = pstart.isoformat(), pend.isoformat()

    cur_q = _query(token, s, e, ["query"], 200)
    prev_q = _query(token, ps, pe, ["query"], 200)
    pages = _query(token, s, e, ["page"], 25)

    c_cur, i_cur = _totals(cur_q)
    c_prev, i_prev = _totals(prev_q)
    ctr = (c_cur / i_cur * 100) if i_cur else 0
    avg_pos = (sum(x["position"] * x["impressions"] for x in cur_q) / i_cur) if i_cur else 0
    try:                                          # → Baserow (хаб статистики)
        import baserow
        baserow.put_rows(baserow.stat_rows("ratescout", "GSC", {
            "clicks": c_cur, "impressions": i_cur, "ctr_pct": ctr, "avg_position": avg_pos}))
    except Exception as _e:                        # noqa: BLE001
        print("baserow GSC skip:", _e)

    L = [f"📈 Search Console — неделя {s} … {e}", ""]
    L.append(f"Клики: {c_cur} ({_pct(c_cur, c_prev)})   Показы: {i_cur} ({_pct(i_cur, i_prev)})")
    L.append(f"CTR: {ctr:.1f}%   Ср. позиция: {avg_pos:.1f}")

    top_q = sorted(cur_q, key=lambda x: x["impressions"], reverse=True)[:10]
    if top_q:
        L += ["", "🔎 Топ-запросы (показы · клики · поз.):"]
        for x in top_q:
            L.append(f"  {x['keys'][0]} — {x['impressions']} · {x['clicks']} · {x['position']:.0f}")

    top_p = sorted(pages, key=lambda x: x["clicks"], reverse=True)[:10]
    if top_p:
        L += ["", "📄 Топ-страницы (клики · показы):"]
        for x in top_p:
            L.append(f"  {_short_url(x['keys'][0])} — {x['clicks']} · {x['impressions']}")

    # «дожать»: 2-я страница выдачи (позиция 8–20) с заметными показами и нулём/малым кликом
    push = [x for x in cur_q if 8 <= x["position"] <= 20 and x["impressions"] >= 15]
    push.sort(key=lambda x: x["impressions"], reverse=True)
    if push:
        L += ["", "🎯 Дожать (поз. 8–20, много показов — усилить страницу/направление):"]
        for x in push[:10]:
            L.append(f"  {x['keys'][0]} — {x['impressions']} показов, поз. {x['position']:.0f}")
    else:
        L += ["", "🎯 Дожать: пока нет запросов на 2-й странице с заметными показами (рано, данные копятся)."]

    return "\n".join(L)


def send_telegram(text):
    tok, chat = os.environ.get("TELEGRAM_TOKEN"), os.environ.get("ALERT_CHAT_ID")
    if not tok or not chat:
        print("TELEGRAM_TOKEN/ALERT_CHAT_ID не заданы — отчёт не отправлен.\n--- отчёт ---\n" + text)
        return
    # Telegram лимит ~4096 символов — при необходимости режем
    for chunk_start in range(0, len(text), 3900):
        data = urllib.parse.urlencode({"chat_id": chat, "text": text[chunk_start:chunk_start + 3900],
                                       "disable_web_page_preview": "true"}).encode()
        try:
            with urllib.request.urlopen(urllib.request.Request(
                    f"https://api.telegram.org/bot{tok}/sendMessage", data=data, method="POST"), timeout=30) as r:
                ok = json.load(r).get("ok")
            print("отчёт отправлен" if ok else "ошибка ответа Telegram")
        except Exception as ex:                    # noqa: BLE001
            print(f"ошибка отправки: {ex}")


def _url_to_pair(url):
    """/obmen/<from>-<to>/ (в т.ч. /en/...) -> (from, to) по каталогу; иначе None."""
    m = re.search(r"/obmen/([a-z0-9-]+)/", url)
    if not m or not _CUR:
        return None
    full = m.group(1)
    for f in _CUR:
        if full.startswith(f + "-"):
            t = full[len(f) + 1:]
            if t in _CUR:
                return (f, t)
    return None


def write_popular(token):
    """popular.json — клики по направлениям /obmen/ из GSC (для ранжирования страницы /napravleniya/)."""
    today = datetime.now(timezone.utc).date()
    end = today - timedelta(days=LAG_DAYS)
    start = end - timedelta(days=27)          # 4 недели — устойчивее к шуму
    rows = _query(token, start.isoformat(), end.isoformat(), ["page"], 1000)
    clicks = {}
    for x in rows:
        pair = _url_to_pair(x["keys"][0])
        if pair and x.get("clicks"):
            clicks[f"{pair[0]}>{pair[1]}"] = clicks.get(f"{pair[0]}>{pair[1]}", 0) + int(x["clicks"])
    out = os.path.join(ROOT, "popular.json")
    json.dump({"clicks": clicks}, open(out, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"popular.json: направлений с кликами {len(clicks)}")


def main():
    sa = os.environ.get("GSC_SA_JSON")
    if not sa:
        print("GSC_SA_JSON не задан — сухой прогон. Скрипт запросил бы Search Console и прислал отчёт в Telegram.")
        print(f"Ресурс (GSC_SITE): {SITE}")
        return 0
    try:
        token = _access_token(sa)
        report = build_report(token)
        write_popular(token)                       # обновляем popular.json для страницы /napravleniya/
    except Exception as ex:                        # noqa: BLE001
        report = f"⚠️ Отчёт Search Console не собрался: {ex}"
        print(report)
    send_telegram(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
