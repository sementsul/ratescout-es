#!/usr/bin/env python3
"""Оптимизация настройки кабинетов через API: форс-перечитка sitemap в GSC + детали диагностики Яндекса.

  GSC:    PUT sitemap (переотправка) — чтобы Google перечитал актуальный sitemap (все URL, включая новые пары).
          Нужен доступ на запись — сервис-аккаунт с правом «Владелец/Full» в Search Console.
  Яндекс: GET диагностика — печатает конкретные проблемы/рекомендации, чтобы знать, что чинить.
          (sitemap Яндекс перечитывает сам; новые URL уже пингуются через IndexNow в деплое.)

Секреты — ТОЛЬКО из окружения: GSC_SA_JSON, GSC_SITE, YANDEX_OAUTH_TOKEN, YANDEX_HOST, TELEGRAM_TOKEN, ALERT_CHAT_ID.
"""
import json
import os
import sys
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))


def _domain():
    try:
        return json.load(open(os.path.join(ROOT, "data.json"), encoding="utf-8"))["site"]["domain"]
    except (OSError, ValueError, KeyError):
        return "ratescout.ru"


_DOMAIN = _domain()
GSC_SITE = os.environ.get("GSC_SITE") or f"https://{_DOMAIN}/"
SITEMAP = f"https://{_DOMAIN}/sitemap.xml"
Y_HOST = (os.environ.get("YANDEX_HOST") or f"https://{_DOMAIN}").rstrip("/")
WM = "https://api.webmaster.yandex.net/v4"


def gsc_resubmit():
    sa = os.environ.get("GSC_SA_JSON")
    if not sa:
        return "🔵 GSC: нет ключа"
    try:
        from google.oauth2 import service_account
        import google.auth.transport.requests
        creds = service_account.Credentials.from_service_account_info(
            json.loads(sa), scopes=["https://www.googleapis.com/auth/webmasters"])   # full — нужна запись
        creds.refresh(google.auth.transport.requests.Request())
        feed = urllib.parse.quote(SITEMAP, safe="")
        url = f"https://www.googleapis.com/webmasters/v3/sites/{urllib.parse.quote(GSC_SITE, safe='')}/sitemaps/{feed}"
        req = urllib.request.Request(url, method="PUT", headers={"Authorization": f"Bearer {creds.token}"})
        code = urllib.request.urlopen(req, timeout=60).status
        return f"🔵 GSC: sitemap переотправлен (HTTP {code}) — Google перечитает все URL."
    except Exception as e:                         # noqa: BLE001
        msg = str(e)[:120]
        hint = " (у сервис-аккаунта нет права записи — дай ему роль «Владелец» в Search Console " \
               "или нажми «Отправить повторно» в Индексирование→Sitemap вручную)" if "403" in msg else ""
        return f"🔵 GSC: переотправка не удалась — {msg}{hint}"


def _yget(url, token):
    req = urllib.request.Request(url, headers={"Authorization": f"OAuth {token}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def yandex_diagnostics():
    token = os.environ.get("YANDEX_OAUTH_TOKEN")
    if not token:
        return "🟡 Яндекс: нет ключа"
    try:
        uid = _yget(f"{WM}/user", token)["user_id"]
        hosts = _yget(f"{WM}/user/{uid}/hosts", token)["hosts"]
        host = next((h for h in hosts if h.get("ascii_host_url", "").rstrip("/") == Y_HOST), None) or \
            next((h for h in hosts if Y_HOST.split("//")[-1] in h.get("ascii_host_url", "")), None)
        hid = urllib.parse.quote(host["host_id"], safe="")
        d = _yget(f"{WM}/user/{uid}/hosts/{hid}/diagnostics/", token)
    except Exception as e:                         # noqa: BLE001
        return f"🟡 Яндекс диагностика: ошибка — {str(e)[:100]}"
    print("DBG diag:", json.dumps(d, ensure_ascii=False)[:900])
    probs = d.get("problems") if isinstance(d, dict) else d
    items = []
    if isinstance(probs, dict):                    # {"TYPE": {...}} или {"TYPE": "PRESENT"}
        for k, v in probs.items():
            st = v.get("state") if isinstance(v, dict) else v
            sev = v.get("severity") if isinstance(v, dict) else "?"
            items.append((sev, k, st))
    elif isinstance(probs, list):
        for p in probs:
            if isinstance(p, dict):
                items.append((p.get("severity", "?"), p.get("problem_type", "?"), p.get("state", "?")))
    active = [i for i in items if str(i[2]).upper() != "ABSENT"]
    if not active:
        return "🟡 Яндекс диагностика: активных проблем нет"
    L = ["🟡 Яндекс диагностика:"]
    for sev, typ, st in active:
        L.append(f"  [{sev}] {typ} — {st}")
    return "\n".join(L)


def send_telegram(text):
    tok, chat = os.environ.get("TELEGRAM_TOKEN"), os.environ.get("ALERT_CHAT_ID")
    if not tok or not chat:
        return
    data = urllib.parse.urlencode({"chat_id": chat, "text": text, "disable_web_page_preview": "true"}).encode()
    try:
        urllib.request.urlopen(urllib.request.Request(
            f"https://api.telegram.org/bot{tok}/sendMessage", data=data, method="POST"), timeout=30)
    except Exception:                              # noqa: BLE001
        pass


def main():
    text = "🔧 Оптимизация кабинетов\n\n" + gsc_resubmit() + "\n\n" + yandex_diagnostics()
    print(text)
    send_telegram(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
