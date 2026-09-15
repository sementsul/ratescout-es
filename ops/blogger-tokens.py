#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Локальная проверка и хранение Blogger OAuth-ключей (запускать У СЕБЯ, не в CI).

Берёт ключи так же, как их берёт blogger_daily.py (переменные окружения
BLOGGER_CLIENT_ID / BLOGGER_CLIENT_SECRET / BLOGGER_REFRESH_TOKEN), меняет
refresh-токен на access-токен и проверяет его запросом к Blogger API
(читает названия трёх блогов — значения ключей при этом нигде не печатаются).

Использование:
    set BLOGGER_CLIENT_ID=... & set BLOGGER_CLIENT_SECRET=... & set BLOGGER_REFRESH_TOKEN=...
    python3 ops/blogger-tokens.py
    # или без env — спросит скрытым вводом и сохранит ответы в .blogger-tokens.json

    python3 ops/blogger-tokens.py --push
    # то же самое + сразу зальёт тройку в GitHub Secrets репо (нужен GH_TOKEN),
    # чтобы workflow blogger.yml мог постить. Значения в лог не попадают.

Файл .blogger-tokens.json — ТОЛЬКО локальный (в .gitignore), в репозиторий не коммитить.
"""
import base64
import getpass
import json
import os
import sys
import urllib.parse
import urllib.request

TOKENS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", ".blogger-tokens.json")
BLOG_IDS = {"es": "4058102092155525402",
            "en": "1472804293788001769",
            "fr": "6430008779499412115"}


def _ask(name, have):
    if have:
        return have
    v = getpass.getpass(f"{name} (скрытый ввод, Enter=пропустить): ").strip()
    return v


def _load():
    cid = os.environ.get("BLOGGER_CLIENT_ID", "")
    sec = os.environ.get("BLOGGER_CLIENT_SECRET", "")
    rtok = os.environ.get("BLOGGER_REFRESH_TOKEN", "")
    if not (cid and sec and rtok):
        try:
            saved = json.load(open(TOKENS_FILE, encoding="utf-8"))
            cid = cid or saved.get("BLOGGER_CLIENT_ID", "")
            sec = sec or saved.get("BLOGGER_CLIENT_SECRET", "")
            rtok = rtok or saved.get("BLOGGER_REFRESH_TOKEN", "")
            if cid:
                print("(частично взято из .blogger-tokens.json)")
        except (OSError, ValueError):
            pass
    return (_ask("BLOGGER_CLIENT_ID", cid),
            _ask("BLOGGER_CLIENT_SECRET", sec),
            _ask("BLOGGER_REFRESH_TOKEN", rtok))


def _save_local(cid, sec, rtok):
    json.dump({"BLOGGER_CLIENT_ID": cid, "BLOGGER_CLIENT_SECRET": sec,
               "BLOGGER_REFRESH_TOKEN": rtok},
              open(TOKENS_FILE, "w", encoding="utf-8"))
    print(f"сохранено локально: {TOKENS_FILE} (в .gitignore, не коммитить)")


def _access_token(cid, sec, rtok):
    data = urllib.parse.urlencode({"client_id": cid, "client_secret": sec,
                                   "refresh_token": rtok,
                                   "grant_type": "refresh_token"}).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token",
                                 data=data, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["access_token"]


def _blog_title(token, blog_id):
    req = urllib.request.Request(
        f"https://www.googleapis.com/blogger/v3/blogs/{blog_id}?fields=name,posts",
        headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.load(r)
    return d.get("name"), (d.get("posts") or {}).get("totalItems")


def _push_secrets(repo, gh_token, cid, sec, rtok):
    from nacl.public import PublicKey, SealedBox
    api = "https://api.github.com"

    def call(method, path, data=None):
        req = urllib.request.Request(
            api + path, method=method,
            data=json.dumps(data).encode() if data is not None else None,
            headers={"Authorization": f"Bearer {gh_token}",
                     "Accept": "application/vnd.github+json",
                     "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, (r.read().decode() or "{}")

    _, raw = call("GET", f"/repos/{repo}/actions/secrets/public-key")
    pk = json.loads(raw)
    pub, key_id = PublicKey(base64.b64decode(pk["key"])), pk["key_id"]
    for name, val in (("BLOGGER_CLIENT_ID", cid),
                      ("BLOGGER_CLIENT_SECRET", sec),
                      ("BLOGGER_REFRESH_TOKEN", rtok)):
        enc = base64.b64encode(SealedBox(pub).encrypt(val.encode())).decode()
        st, _ = call("PUT", f"/repos/{repo}/actions/secrets/{name}",
                     {"encrypted_value": enc, "key_id": key_id})
        print(("  OK " if st in (201, 204) else f"  ERR {st} ") + name)


def main():
    do_push = "--push" in sys.argv
    repo = "sementsul/ratescout-es"
    for a in sys.argv[1:]:
        if a.startswith("--repo="):
            repo = a.split("=", 1)[1]
    cid, sec, rtok = _load()
    if not (cid and sec and rtok):
        sys.exit("Нужны все три значения — без них проверить нечего.")
    _save_local(cid, sec, rtok)
    try:
        token = _access_token(cid, sec, rtok)
    except Exception as e:                            # noqa: BLE001
        sys.exit(f"OAuth-обмен не удался (ключи неверные или отозваны): {str(e)[:150]}")
    print("access-токен получен, проверяю блоги:")
    ok = True
    for lang, bid in BLOG_IDS.items():
        try:
            name, total = _blog_title(token, bid)
            print(f"  [{lang}] {bid} → «{name}» (постов: {total})")
        except Exception as e:                        # noqa: BLE001
            ok = False
            print(f"  [{lang}] {bid} → ОШИБКА: {str(e)[:120]}")
    if not ok:
        sys.exit("Ключи рабочие, но не все блоги доступны этому аккаунту.")
    print("Ключи в порядке — workflow blogger.yml сможет постить во все 3 блога.")
    if do_push:
        gh = os.environ.get("GH_TOKEN") or getpass.getpass("GitHub token: ").strip()
        _push_secrets(repo, gh, cid, sec, rtok)
        print("Готово. Запусти workflow blogger.yml вручную для первой проверки.")


if __name__ == "__main__":
    main()
