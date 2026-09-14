#!/usr/bin/env python3
"""Отправка списка URL в IndexNow (мгновенная переиндексация Яндекс/Bing/Seznam).

Читает готовый dist/sitemap.xml, шлёт все <loc> одним запросом на api.indexnow.org.
Ключ — публичный (лежит файлом на сайте: /<key>.txt). Запускать в CI ПОСЛЕ деплоя
и НЕ на почасовом cron (иначе спам) — только при реальных изменениях контента.
"""
import json
import os
import re
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))


def _domain():
    try:
        return json.load(open(os.path.join(ROOT, "data.json"), encoding="utf-8"))["site"]["domain"]
    except (OSError, ValueError, KeyError):
        return "ratescout.ru"


HOST = os.environ.get("INDEXNOW_HOST") or _domain()
KEY = "b394aeced6a92ed48a09e2bd30099905"
ENDPOINT = "https://api.indexnow.org/indexnow"


def main():
    sm = os.path.join(ROOT, "dist", "sitemap.xml")
    if not os.path.exists(sm):
        print("нет dist/sitemap.xml — пропускаю IndexNow")
        return
    urls = re.findall(r"<loc>(.*?)</loc>", open(sm, encoding="utf-8").read())
    if not urls:
        print("в sitemap нет URL — пропускаю")
        return
    payload = {
        "host": HOST,
        "key": KEY,
        "keyLocation": f"https://{HOST}/{KEY}.txt",
        "urlList": urls[:10000],
    }
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print(f"IndexNow: отправлено {len(payload['urlList'])} URL, ответ {r.status}")
    except urllib.error.HTTPError as e:
        # 200/202 — ок; прочее логируем, но не валим билд
        print(f"IndexNow HTTP {e.code}: {e.reason}")
    except Exception as e:  # noqa: BLE001 — не роняем деплой из-за пинга
        print(f"IndexNow ошибка (не критично): {e}")


if __name__ == "__main__":
    main()
