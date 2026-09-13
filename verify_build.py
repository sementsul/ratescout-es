#!/usr/bin/env python3
"""Smoke-проверка собранного dist/ ПЕРЕД деплоем.
Ловит логически битую, но «собравшуюся» сборку (пустые/сломанные страницы, остаточные шаблон-токены,
невалидный JSON-LD, полу-пустой билд). exit 1 → шаг деплоя падает → на проде остаётся прошлая версия.
Ставится в deploy.yml между guard-ключа и upload-pages-artifact. keep-alive (data-push) идёт выше → не страдает.
"""
import os, sys, re, json, glob

DIST = "dist"
errors = []

def need(cond, msg):
    if not cond:
        errors.append(msg)

# 1) Ключевые файлы есть и не подозрительно малы
for f, minsize in [("index.html", 2000), ("sitemap.xml", 500), ("robots.txt", 30), ("llms.txt", 200)]:
    p = os.path.join(DIST, f)
    need(os.path.exists(p) and os.path.getsize(p) >= minsize, f"{f}: отсутствует или слишком мал")

# 2) Пример «денежной» страницы валюты содержит ожидаемые маркеры
btc = os.path.join(DIST, "valuta/bitcoin/index.html")
if os.path.exists(btc):
    h = open(btc, encoding="utf-8").read()
    need("BestChange" in h, "valuta/bitcoin: нет 'BestChange'")
    need('class="answer"' in h, "valuta/bitcoin: нет answer-first блока")
else:
    errors.append("valuta/bitcoin/index.html отсутствует")

# 3) Sitemap содержит URL
sm = os.path.join(DIST, "sitemap.xml")
if os.path.exists(sm):
    need("<loc>" in open(sm, encoding="utf-8").read(), "sitemap.xml без <loc>")

# 4) Нет остаточных шаблон-токенов/битых значений (выборка ключевых страниц)
BAD = ["{{", "None ₽", "{tmin}", "{slug}", ">None<", "NaN ₽"]
sample = (glob.glob(os.path.join(DIST, "valuta/*/index.html"))[:300]
          + glob.glob(os.path.join(DIST, "obmen/*/index.html"))[:300]
          + [os.path.join(DIST, "index.html")])
for p in sample:
    if not os.path.exists(p):
        continue
    h = open(p, encoding="utf-8", errors="ignore").read()
    for m in BAD:
        if m in h:
            errors.append(f"{os.path.relpath(p, DIST)}: битый маркер '{m}'")
            break

# 5) JSON-LD парсится на ключевых страницах
for p in [os.path.join(DIST, "index.html"), btc]:
    if not os.path.exists(p):
        continue
    h = open(p, encoding="utf-8").read()
    for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', h, re.S):
        try:
            json.loads(block)
        except Exception as e:
            errors.append(f"{os.path.relpath(p, DIST)}: невалидный JSON-LD ({str(e)[:40]})")
            break

# 6) Защита от полу-пустой сборки
n = len(glob.glob(os.path.join(DIST, "**", "index.html"), recursive=True))
_langs_n = 1
try:
    _langs_n = len(json.load(open("data.json", encoding="utf-8")).get("site", {}).get("langs", ["ru"]))
except Exception:
    pass
need(n >= (1000 if _langs_n > 1 else 500), f"подозрительно мало страниц: {n}")

if errors:
    print("🔴 SMOKE-ПРОВЕРКА dist/ ПРОВАЛЕНА — деплой отменяется:")
    for e in errors[:20]:
        print("  •", e)
    sys.exit(1)
print(f"✅ smoke-проверка dist/ пройдена ({n} страниц)")
