#!/usr/bin/env python3
"""Создание НОВЫХ постов в Blogger (Google Blogger API v3) — для статей пайплайна.

В отличие от blogger_daily.py (обновляет вечные посты-сводки PATCH), здесь каждая
статья = новый пост POST с метками и ссылкой на страницу статьи на сайте.
Без секретов — сухой прогон (печатает заголовок и ссылку, не публикует).
"""
import html
import json
import os
import re
import urllib.parse
import urllib.request

CID = os.environ.get("BLOGGER_CLIENT_ID")
CSEC = os.environ.get("BLOGGER_CLIENT_SECRET")
RTOK = os.environ.get("BLOGGER_REFRESH_TOKEN")

# Блоги по языкам (те же секреты, что в blogger.yml).
BLOG_IDS = {
    "es": os.environ.get("BLOGGER_ES_BLOG_ID", ""),
    "en": os.environ.get("BLOGGER_EN_BLOG_ID", ""),
    "fr": os.environ.get("BLOGGER_FR_BLOG_ID", ""),
    "ru": os.environ.get("BLOGGER_RU_BLOG_ID") or os.environ.get("BLOGGER_BLOG_ID", ""),
}

# Куда ведёт ссылка «Читать на сайте» из поста.
SITE_URL = {
    "es": "https://ratescout.oc.com.ar",
    "en": "https://ratescout.ru/en",
    "fr": "https://ratescout.info.gf",
    "ru": "https://ratescout.ru",
}

READ_MORE = {
    "ru": "Читать полностью на сайте",
    "es": "Leer el artículo completo",
    "en": "Read the full article",
    "fr": "Lire l'article complet",
}


def access_token():
    data = urllib.parse.urlencode({"client_id": CID, "client_secret": CSEC,
                                   "refresh_token": RTOK,
                                   "grant_type": "refresh_token"}).encode()
    with urllib.request.urlopen(urllib.request.Request("https://oauth2.googleapis.com/token",
                                                      data=data, method="POST"), timeout=30) as r:
        return json.load(r)["access_token"]


def md_to_html(md, lang="es"):
    """Лёгкий markdown→HTML для постов (заголовки, таблицы не трогаем — их нет в черновиках)."""
    out = []
    for para in re.split(r"\n\s*\n", md.strip()):
        para = para.strip()
        if not para:
            continue
        if para.startswith("### "):
            out.append(f"<h3>{html.escape(para[4:])}</h3>")
            continue
        if para.startswith("## "):
            out.append(f"<h2>{html.escape(para[3:])}</h2>")
            continue
        if para.startswith("# "):
            out.append(f"<h2>{html.escape(para[2:])}</h2>")
            continue
        if para.startswith("|"):
            rows = [r.strip().strip("|").split("|") for r in para.splitlines() if "|" in r]
            rows = [[c.strip() for c in row] for row in rows if not re.match(r"^[\s|:-]+$", r)]
            if len(rows) >= 2:
                th = "".join(f"<th style='padding:6px 10px;text-align:left'>{html.escape(c)}</th>"
                             for c in rows[0])
                tr = "".join("<tr>" + "".join(
                    f"<td style='padding:6px 10px'>{html.escape(c)}</td>" for c in row) + "</tr>"
                    for row in rows[1:])
                out.append(f"<table style='border-collapse:collapse;width:100%'><thead><tr>{th}</tr></thead>"
                           f"<tbody>{tr}</tbody></table>")
                continue
        if all(l.startswith(("- ", "* ")) for l in para.splitlines()):
            li = "".join(f"<li>{html.escape(l[2:])}</li>" for l in para.splitlines())
            out.append(f"<ul>{li}</ul>")
            continue
        if re.match(r"^(\d+[.)]\s+.+\n?)+$", para):
            li = "".join(f"<li>{html.escape(re.sub(r'^\\d+[.)]\\s+', '', l))}</li>"
                         for l in para.splitlines())
            out.append(f"<ol>{li}</ol>")
            continue
        # инлайн: **жирный**, ссылки [t](u)
        p = html.escape(para).replace("\n", "<br>")
        p = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", p)
        p = re.sub(r"\[([^\]]+)\]\((/[^)]+)\)",
                   lambda m, _s=SITE_URL.get(lang, SITE_URL["es"]): f"<a href='{_s}{m.group(2)}'>{m.group(1)}</a>", p)
        out.append(f"<p>{p}</p>")
    return "".join(out)


def find_post_by_title(blog, token, title):
    """URL существующего поста с ТОЧНО таким заголовком (защита от дублей при ретраях)."""
    q = urllib.parse.urlencode({"q": title, "maxResults": 5, "fields": "items(title,url)"})
    req = urllib.request.Request(
        f"https://www.googleapis.com/blogger/v3/blogs/{blog}/posts?{q}",
        headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            for it in json.load(r).get("items", []):
                if it.get("title", "").strip() == title.strip():
                    return it.get("url", "")
    except Exception:  # noqa: BLE001 — поиск необязателен, идём создавать
        pass
    return ""


def create_post(lang, title, md_body, slug="", labels=None, dry=False, read_more=None):
    """Создать новый пост. Возвращает URL поста (или '[dry-run]' без секретов).

    read_more: URL ссылки «Читать полностью →» (по умолчанию — корень сайта языка);
    None — без ссылки (для Blogger-only обзоров без страницы на сайте).
    """
    blog = BLOG_IDS.get(lang, "")
    site = SITE_URL.get(lang, SITE_URL["es"])
    if read_more is None and slug:
        read_more = f"{site}/blog/{slug}/"
    body_html = md_to_html(md_body, lang)
    if read_more:
        more = READ_MORE.get(lang, READ_MORE["es"])
        body_html += f"<p><b><a href='{read_more}'>{more} →</a></b></p>"
    content = body_html
    if dry or not all([CID, CSEC, RTOK, blog]):
        print(f"[dry-run] blog={lang} title={title}" + (f"\n  → {read_more}" if read_more else ""))
        return "[dry-run]"
    payload = json.dumps({"kind": "blogger#post", "title": title, "content": content,
                          "labels": labels or ["RateScout"]}).encode()
    token = access_token()
    dup = find_post_by_title(blog, token, title)
    if dup:
        print(f"[{lang}] такой пост уже есть, дубль не создаю: {dup}")
        return dup
    url = f"https://www.googleapis.com/blogger/v3/blogs/{blog}/posts/"
    req = urllib.request.Request(url, data=payload, method="POST",
                                 headers={"Authorization": f"Bearer {token}",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=40) as r:
        res = json.load(r)
    print(f"[{lang}] пост создан: {res.get('url')}")
    return res.get("url", "")
