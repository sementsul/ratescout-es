#!/usr/bin/env python3
"""Черновики контента через OpenRouter (бесплатные модели) — БЕЗ автопубликации.

Деньги/финансы = YMYL: модель НЕ должна выдумывать курсы, резервы и комиссии.
Цифры — только из rates.json при сборке; LLM пишет прозу, человек проверяет.
Результат — drafts/<slug>.md (локально, в .gitignore). Проверенный текст
отправляешь боту в Telegram (article_intake.py) либо кладёшь в articles/ сам.

Использование:
    python llm_draft.py --topic "Что такое спред при обмене" --lang ru
    python llm_draft.py --translate articles/slippage.md --to es
    python llm_draft.py --social --text "Дайджест курсов за сутки..." --lang ru

Модель: OPENROUTER_MODEL (по умолчанию qwen/qwen3-next-80b-a3b-instruct:free).
Альтернативы :free — openai/gpt-oss-20b:free, google/gemma-4-31b-it:free,
либо авто-роутер openrouter/free. Ключ: OPENROUTER_API_KEY.
"""
import argparse
import os
import re
import sys
from datetime import date

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from llm import chat  # noqa: E402

DRAFT_DIR = os.path.join(ROOT, "drafts")

ARTICLE_SYS = (
    "Ты — редактор справочника RateScout о курсах обмена криптовалют. "
    "Пишешь на языке {lang}. Формат ответа: frontmatter (---, title, description, "
    "date: {today}, slug: {slug}) + markdown-статья 400–700 слов: H1, 2–4 раздела H2, "
    "1 таблица или список. Внутренние ссылки — только на /blog/<slug>/ и /valuta/<slug>/. "
    "СТРОГО: никаких конкретных курсов, резервов, процентов комиссий и дат — только "
    "слова 'примерно', 'зависит от обменника/сети'. Никаких финансовых рекомендаций "
    "('покупайте'), только нейтральное объяснение. Без рекламы конкретных обменников."
)

TRANSLATE_SYS = (
    "Ты — переводчик справочника RateScout. Переведи статью на язык {lang}, сохранив "
    "frontmatter (title/description/date/slug переведи title/description, slug латиницей "
    "через дефис), markdown-структуру и внутренние ссылки как есть. "
    "Не выдумывай цифры. Нейтральный тон, без рекламы."
)

SOCIAL_SYS = (
    "Ты — SMM RateScout. Сожми текст в пост до 500 символов на языке {lang}: "
    "1-2 коротких абзаца + ссылка-плейсхолдер {{URL}}. Живо, без кликбейта, "
    "без конкретных курсов и обещаний выгоды. 1-2 хештега."
)


def slugify(text):
    tr = {"а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
          "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
          "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
          "ф": "f", "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "shch",
          "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya"}
    text = "".join(tr.get(c, c) for c in (text or "").lower())
    return (re.sub(r"[^a-z0-9]+", "-", text).strip("-") or "draft")[:60].strip("-")


def save(slug, text):
    os.makedirs(DRAFT_DIR, exist_ok=True)
    path = os.path.join(DRAFT_DIR, f"{slug}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(f"черновик → {os.path.relpath(path, ROOT)} (проверь и отправь боту / положи в articles/)")
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", help="тема статьи")
    ap.add_argument("--translate", help="путь к articles/*.md для перевода")
    ap.add_argument("--to", default="es", help="язык перевода (по умолчанию es)")
    ap.add_argument("--social", action="store_true", help="сжать текст в пост")
    ap.add_argument("--text", default="", help="текст для --social")
    ap.add_argument("--lang", default="ru")
    ap.add_argument("--model", default=None)
    a = ap.parse_args()

    if a.social:
        if not a.text:
            ap.error("--social требует --text")
        out = chat([{"role": "system", "content": SOCIAL_SYS.format(lang=a.lang)},
                    {"role": "user", "content": a.text}], model=a.model, max_tokens=600)
        if out:
            print(out)
        return
    if a.translate:
        src = open(os.path.join(ROOT, a.translate) if not os.path.isabs(a.translate) else a.translate,
                   encoding="utf-8").read()
        out = chat([{"role": "system", "content": TRANSLATE_SYS.format(lang=a.to)},
                    {"role": "user", "content": src}], model=a.model, max_tokens=4000)
        if out:
            m = re.search(r"^slug:\s*(.+)$", out, re.M)
            save((m.group(1).strip() if m else slugify(a.translate)) + f"-{a.to}", out)
        return
    if a.topic:
        slug = slugify(a.topic)
        out = chat([{"role": "system", "content": ARTICLE_SYS.format(
                        lang=a.lang, today=date.today().isoformat(), slug=slug)},
                    {"role": "user", "content": f"Тема: {a.topic}"}],
                   model=a.model, max_tokens=4000)
        if out:
            save(slug, out)
        return
    ap.error("нужен --topic, --translate или --social")


if __name__ == "__main__":
    main()
