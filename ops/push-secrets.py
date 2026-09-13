#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Заливка Actions-секретов в репозиторий ES-сайта (по умолчанию sementsul/ratescout-es).

Почему так: GitHub API НЕ отдаёт значения секретов (только имена) — их нельзя
"скопировать" скриптом из старого репо. Поэтому значения вводятся ЛОКАЛЬНО
(ввод скрыт) и отправляются только в GitHub API в зашифрованном виде.

Использование:
    python3 ops/push-secrets.py
    # спросит токен (или задай GH_TOKEN / сделай gh auth login),
    # затем значения; Enter — пропустить.
    # значение вида @C:\\path\\file.json — прочитать из файла (удобно для GSC_SA_JSON).

Механика: если есть `gh` — через него; иначе pip-пакет pynacl (ставится сам).
"""

import argparse
import base64
import getpass
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request

API = "https://api.github.com"

NEEDED = [
    ("BESTCHANGE_API_KEY",
     "Партнёрский ключ BestChange (БЕЗ НЕГО НЕТ КУРСОВ)"),
    ("BESTCHANGE_RATES_URL",
     "URL экспорта курсов BestChange с плейсхолдером {key}"),
]

OPTIONAL = [
    ("COINGECKO_KEY",
     "CoinGecko API (необязательно — market-данные ходят и без ключа)"),
    ("TELEGRAM_TOKEN",
     "Токен TG-бота для дайджестов (необязательно)"),
    ("TELEGRAM_CHANNEL",
     "TG-канал, напр. @ratescout_es (необязательно)"),
    ("TELEGRAM_CHANNEL_EN",
     "TG-канал EN (можно пропустить)"),
    ("GSC_SA_JSON",
     "Service-account JSON для Search Console (можно @путь-к-файлу)"),
    ("GSC_SITE",
     "Property в GSC, напр. https://ratescout.oc.com.ar/"),
]


def api(method, path, token, data=None):
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(
        API + path, data=body, method=method,
        headers={"Authorization": "Bearer " + token,
                 "Accept": "application/vnd.github+json",
                 "Content-Type": "application/json",
                 "User-Agent": "ratescout-es-ops"})
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read().decode() or "{}"
            return r.status, json.loads(raw)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]


def ensure_nacl():
    try:
        import nacl.public  # noqa: F401
        return True
    except ImportError:
        pass
    print("Ставлю pynacl для шифрования секретов...")
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "pynacl"])
    try:
        import nacl.public  # noqa: F401
        return True
    except ImportError:
        return False


def put_nacl(repo, name, value, token, pub, key_id):
    from nacl.public import SealedBox
    enc = base64.b64encode(SealedBox(pub).encrypt(value.encode())).decode()
    st, out = api("PUT", "/repos/%s/actions/secrets/%s" % (repo, name),
                  token, {"encrypted_value": enc, "key_id": key_id})
    return st in (201, 204), "%s %s" % (st, out)


def put_gh(repo, name, value, token):
    env = dict(os.environ)
    if token:
        env["GH_TOKEN"] = token
        env["GITHUB_TOKEN"] = token
    p = subprocess.run(
        ["gh", "secret", "set", name, "--repo", repo, "--body", value],
        capture_output=True, text=True, env=env)
    return p.returncode == 0, (p.stderr or p.stdout)[:200]


def ask(hint, name):
    v = getpass.getpass("%s\n  %s (Enter=пропустить): " % (hint, name)).strip()
    if v.startswith("@"):
        with open(os.path.expanduser(v[1:]), encoding="utf-8") as f:
            v = f.read().strip()
        print("  (прочитано из файла, символов: %d)" % len(v))
    return v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--token", default=os.environ.get("GH_TOKEN", ""))
    ap.add_argument("--repo", default="sementsul/ratescout-es")
    a = ap.parse_args()

    use_gh = shutil.which("gh") is not None
    print("Backend:", "gh CLI" if use_gh else "pynacl/API")

    token = a.token or getpass.getpass("GitHub token (нужны права repo; пусто = уже есть gh auth): ")
    if not use_gh and not token:
        sys.exit("Без токена никак.")
    if token:
        st, me = api("GET", "/user", token)
        if st != 200:
            sys.exit("Токен не подошёл: %s %s" % (st, me))
        print("OK, владелец токена:", me.get("login"))

    if use_gh:
        def put(name, value):
            ok, msg = put_gh(a.repo, name, value, token)
            print(("  OK  " if ok else "  ERR: " + msg + " ") + name)
            return ok
    else:
        if not ensure_nacl():
            sys.exit("Не встал pynacl — поставь вручную: pip install pynacl")
        from nacl.public import PublicKey
        st, pk = api("GET", "/repos/%s/actions/secrets/public-key" % a.repo, token)
        if st != 200:
            sys.exit("Нет доступа к репо %s: %s %s" % (a.repo, st, pk))
        pub = PublicKey(base64.b64decode(pk["key"]))
        key_id = pk["key_id"]

        def put(name, value):
            ok, msg = put_nacl(a.repo, name, value, token, pub, key_id)
            print(("  OK  " if ok else "  ERR: " + msg + " ") + name)
            return ok

    print("\n--- ОБЯЗАТЕЛЬНЫЕ ---")
    for name, hint in NEEDED:
        v = ask(hint, name)
        if v:
            put(name, v)
        else:
            print("  SKIP " + name + " (без него не будет курсов!)")

    print("\n--- НЕОБЯЗАТЕЛЬНЫЕ ---")
    for name, hint in OPTIONAL:
        v = ask(hint, name)
        if v:
            put(name, v)
        else:
            print("  SKIP " + name)

    st, lst = api("GET", "/repos/%s/actions/secrets?per_page=100" % a.repo,
                  token or "x")
    names = sorted(s["name"] for s in lst.get("secrets", [])) if st == 200 else []
    print("\nИтого секретов в %s: %d" % (a.repo, len(names)))
    print(", ".join(names) if names else "(список недоступен)")
    print("\nГотово. Следующий почасовой деплой подхватит новые значения.")


if __name__ == "__main__":
    main()
