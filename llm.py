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
import time
import urllib.request

API_URL = "https://openrouter.ai/api/v1/chat/completions"
# Дефолт проверен 2026-09-17: отвечает чисто, без рассуждений вслух.
# Запасные :free (узнать живых: GET /models, фильтр :free):
#   nvidia/nemotron-3-super-120b-a12b:free — ок, но иногда "думает вслух"
#   nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free — ок
# Мёртвые на 2026-09-17: qwen/qwen3-next-80b-*:free (404), inkling-small (403 agentic-only),
#   liquid/lfm, cohere/north-mini-code (пустой content).
# Пустая переменная окружения = не задана (GitHub подставляет "" за отсутствующий секрет).
DEFAULT_MODEL = (
    os.environ.get("OPENROUTER_MODEL") or "nex-agi/nex-n2.5-mini:free"
)
FALLBACK_MODELS = [
    m.strip()
    for m in (
        os.environ.get("OPENROUTER_FALLBACKS")
        or "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free,"
        "nvidia/nemotron-3-super-120b-a12b:free"
    ).split(",")
    if m.strip()
]


def _post(messages, model, max_tokens, temperature, timeout, headers):
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    req = urllib.request.Request(
        API_URL, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def chat(messages, model=None, max_tokens=2000, temperature=0.7, timeout=120):
    """Отправить messages в OpenRouter, вернуть текст ответа.

    Без OPENROUTER_API_KEY — сухой прогон (возвращает "" и пишет в stdout).
    Free-tier часто отдаёт 429 (перегружен общий пул): делаем до 3 попыток
    с паузой + перебираем запасные модели. Не вышло — RuntimeError с понятным текстом.
    """
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        print("llm: нет OPENROUTER_API_KEY — сухой прогон, возвращаю пусто")
        return ""
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
    models = [model or DEFAULT_MODEL] + [m for m in FALLBACK_MODELS if m != (model or DEFAULT_MODEL)]
    last_err = "неизвестная ошибка"
    for mi, m in enumerate(models):
        for attempt in range(3):
            try:
                data = _post(messages, m, max_tokens, temperature, timeout, headers)
                text = (data.get("choices") or [{}])[0].get("message", {}).get("content")
                if text and text.strip():
                    return text.strip()
                last_err = f"{m}: пустой ответ"
                break  # пустой ответ ретраями не лечится — следующая модель
            except Exception as e:
                last_err = f"{m}: {e}"
                time.sleep(5 * (attempt + 1))
        print(f"llm: модель {m} не ответила ({last_err[:120]}), пробую следующую…")
    raise RuntimeError(f"OpenRouter: все модели заняты/недоступны. Последняя ошибка: {last_err[:300]}")


if __name__ == "__main__":
    import sys

    print(chat([{"role": "user", "content": " ".join(sys.argv[1:]) or "Привет"}]))
