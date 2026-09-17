#!/usr/bin/env python3
"""Минимальный клиент OpenRouter (только stdlib, без зависимостей).

Ключ — ТОЛЬКО из окружения OPENROUTER_API_KEY (.env локально / GitHub Secret в CI).
Никогда не коммитить ключ в репозиторий. Бесплатные модели — со суффиксом :free,
либо авто-роутер "openrouter/free". Модель задаётся OPENROUTER_MODEL.

Пример:
    from llm import chat
    text = chat([{"role": "user", "content": "Привет"}])
"""
import json
import os
import urllib.request

API_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = os.environ.get(
    "OPENROUTER_MODEL", "qwen/qwen3-next-80b-a3b-instruct:free"
)


def chat(messages, model=None, max_tokens=2000, temperature=0.7, timeout=120):
    """Отправить messages в OpenRouter, вернуть текст ответа.

    Без OPENROUTER_API_KEY — сухой прогон (возвращает "" и пишет в stdout).
    Ошибки API пробрасываются как RuntimeError (вызывающий код решает: ретрай/пропуск).
    """
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        print("llm: нет OPENROUTER_API_KEY — сухой прогон, возвращаю пусто")
        return ""
    payload = {
        "model": model or DEFAULT_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    # OpenRouter просит идентифицировать приложение (необязательно, но повышает лимиты free-tier)
    site = os.environ.get("OPENROUTER_SITE_URL", "https://ratescout.ru")
    app = os.environ.get("OPENROUTER_APP_NAME", "RateScout drafts")
    if site:
        headers["HTTP-Referer"] = site
    if app:
        headers["X-Title"] = app
    req = urllib.request.Request(
        API_URL, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.load(r)
    except Exception as e:
        raise RuntimeError(f"OpenRouter error: {e}")
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, AttributeError) as e:
        raise RuntimeError(f"OpenRouter bad response: {data!r:.300} ({e})")


if __name__ == "__main__":
    import sys

    print(chat([{"role": "user", "content": " ".join(sys.argv[1:]) or "Привет"}]))
