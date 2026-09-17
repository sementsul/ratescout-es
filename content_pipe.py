#!/usr/bin/env python3
"""Контент-пайплайн: темы → черновик → антидубль → самопроверка ИИ → публикация.

Цепочка (каждый шаг — ворота, дальше не идём при провале):
  draft-next      взять следующее todo из topics.json → dup-check темы → черновик в drafts/
  dup-check F     схожесть с articles/*, drafts/* (Жаккар по словам + совпадение slug)
  selfcheck F     второй проход ИИ: нет ли выдуманных цифр, тон, ссылки, сравнение с корпусом
  publish F       --langs es[,en,fr] (+перевод) → articles/<lang>/ → новые посты в Blogger
  market-daily    ИИ-анализ рынка за сутки (цифры — только из history.json, считает скрипт)
  market-weekly   то же за 7 дней

Публикация — только с флагом --yes (в workflow он есть, руками — осознанно).
Без OPENROUTER_API_KEY шаги с ИИ — сухой прогон. Без BLOGGER_*-секретов publish —
сухой прогон (файлы в articles/ всё равно кладутся только с --yes).
"""
import argparse
import json
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from llm import chat  # noqa: E402
from blogger_post import create_post  # noqa: E402

TOPICS_FILE = os.path.join(ROOT, "topics.json")
LOG_FILE = os.path.join(ROOT, "content_log.json")
DRAFT_DIR = os.path.join(ROOT, "drafts")
ART_DIR = os.path.join(ROOT, "articles")

STOP = set("""и в на с по к о у же не от для при это как что или его ее их мы вы они
всего между через над под уже также можно только если есть будет было быть
the and for with from that this are was have has not but you your les des une
dans pour sur les plus avec pas est sont que qui los las una por con para del
al como más pero sus este esta son fue han""".split())

DUP_WARN = 0.35   # схожесть Жаккара: выше — предупреждение
DUP_BLOCK = 0.55  # выше — жёсткий блок (дубль)

MAJORS = ["bitcoin", "ethereum", "tether-trc20", "solana", "tron",
          "toncoin", "litecoin", "dogecoin", "xrp", "usdc"]

ARTICLE_SYS = (
    "Ты — редактор справочника RateScout о курсах обмена криптовалют. "
    "Пишешь на языке {lang}. Формат: frontmatter (---, title, description, "
    "date: {today}, slug: {slug}) + markdown 400–700 слов: H1, 2–4 H2, 1 таблица/список. "
    "Внутренние ссылки — только /blog/<slug>/ и /valuta/<slug>/. "
    "СТРОГО: никаких конкретных курсов, резервов, процентов и дат — только "
    "'примерно', 'зависит от обменника/сети'. Без финансовых рекомендаций и рекламы."
    + (" ДАЛЕЕ — существующие статьи (НЕ повторяй их, дополняй):\n{corpus}" if "{corpus}" else "")
)

SELFCHECK_SYS = (
    "Ты — контролёр качества RateScout. Проверь статью и ответь СТРОГО в формате:\n"
    "VERDICT: PASS или FAIL\nREASONS: список проблем через '; ' (или 'нет')\n"
    "Критерии FAIL: (1) конкретные курсы/резервы/проценты/даты в ТЕЛЕ статьи, "
    "которых нет в блоке ФАКТЫ (frontmatter date/slug — служебные, разрешены; "
    "дата из ФАКТОВ 'Сегодня' в теле обзора — разрешена; "
    "описание героя дня словами без цифр — разрешено); "
    "(2) финансовые рекомендации ('покупайте', 'выгодно вложить'); (3) реклама обменников; "
    "(4) ссылки /blog/ не из списка СЛАГИ, ссылки не на /blog/ и не на /valuta/; "
    "(5) тема дублирует статью из СУЩЕСТВУЮЩИЕ (пересказ теми же словами).\n"
    "СУЩЕСТВУЮЩИЕ (заголовки):\n{corpus}\nСЛАГИ статей:\n{slugs}\n"
    "ФАКТЫ (единственные разрешённые цифры):\n{facts}"
)

MARKET_SYS = (
    "Ты — аналитик RateScout. Напиши {period} обзор рынка на языке {lang} по таблице ФАКТЫ "
    "(цены USDT, изменения посчитаны скриптом — используй ТОЛЬКО их, ничего не выдумывай). "
    "slug и title возьми ТОЧНО из сообщения пользователя, не придумывай свои. "
    "Формат: frontmatter (---, title, description, date: {today}, slug: {slug}) + 300–500 слов: "
    "лидеры роста/падения, стейблкоины отдельно, 1 абзац 'что это значит для обмена' "
    "(без торговых рекомендаций). Если дано ВЧЕРА — свяжи повествование с ним "
    "(разворот/продолжение/затухание), не копируй вчерашние формулировки. "
    "Если дан ГЕРОЙ ДНЯ — включи мини-раздел о проекте (сеть, назначение; без цифр цен). "
    "Не ссылайся на сам этот обзор. "
    "Ссылки — только /valuta/<slug>/ и /blog/<slug>/."
)


# ---------- корпус и схожесть ----------

def words(text):
    return {w for w in re.findall(r"[a-zа-яё]+", text.lower()) if len(w) > 3 and w not in STOP}


def corpus_index():
    """[(slug, title, words)] по articles/* + drafts/*."""
    items = []
    for base in [ART_DIR, DRAFT_DIR]:
        if not os.path.isdir(base):
            continue
        for dp, _, fns in os.walk(base):
            for fn in fns:
                if not fn.endswith(".md"):
                    continue
                p = os.path.join(dp, fn)
                try:
                    raw = open(p, encoding="utf-8").read()
                except OSError:
                    continue
                m = re.search(r"^title:\s*(.+)$", raw, re.M)
                title = m.group(1).strip() if m else fn
                m2 = re.search(r"^slug:\s*(.+)$", raw, re.M)
                slug = m2.group(1).strip() if m2 else fn[:-3]
                items.append((slug, title, words(title + " " + raw[:2000]), p))
    return items


def dup_check(title, body="", slug="", skip=""):
    """(статус, схожесть, совпавший_файл). Статус: ok | warn | block."""
    corp = corpus_index()
    mine = words(title + " " + body[:2000]) or words(title)
    best, bestf = 0.0, ""
    skip = os.path.abspath(skip) if skip else ""
    for s, t, w, p in corp:
        if skip and os.path.abspath(p) == skip:
            continue  # сам себя не проверяем
            return "block", 1.0, p
        j = len(mine & w) / max(1, len(mine | w))
        if j > best:
            best, bestf = j, f"{p} [{t[:60]}]"
    if best >= DUP_BLOCK:
        return "block", best, bestf
    if best >= DUP_WARN:
        return "warn", best, bestf
    return "ok", best, bestf


def corpus_titles(limit=60):
    return "\n".join(f"- {t}" for _, t, _, _ in corpus_index()[:limit])


# ---------- topics.json ----------

def load_topics():
    return json.load(open(TOPICS_FILE, encoding="utf-8"))["topics"]


def save_topics(topics):
    json.dump({"topics": topics}, open(TOPICS_FILE, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


def log(entry):
    try:
        l = json.load(open(LOG_FILE, encoding="utf-8"))
    except (OSError, ValueError):
        l = []
    l.append({"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), **entry})
    json.dump(l, open(LOG_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


# ---------- рыночные цифры (считает скрипт, НЕ модель) ----------

def _pts(series):
    """[(datetime, value)] — понимает 'YYYY-MM-DD' и 'YYYY-MM-DD HH:MM'."""
    out = []
    for ts, v in series:
        dt = None
        for f in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(ts, f)
                break
            except (ValueError, TypeError):
                pass
        if dt is not None and isinstance(v, (int, float)) and v:
            out.append((dt, v))
    return out


def market_stats(days=1, ref_days_ago=0):
    """Цифры считает скрипт, НЕ модель. ref_days_ago=1 — срез 'вчера в это время' (для связности)."""
    try:
        hist = json.load(open(os.path.join(ROOT, "history.json"), encoding="utf-8"))["series"]
    except (OSError, ValueError, KeyError):
        return "", [], {}
    try:
        kinds = json.load(open(os.path.join(ROOT, "currencies.json"), encoding="utf-8"))["currencies"]
    except (OSError, ValueError, KeyError):
        kinds = {}
    # якорь «конец окна»: глобальный максимум минус сдвиг (для вчерашнего среза)
    all_ts = [dt for pts in hist.values() for dt, _ in _pts(pts)]
    if not all_ts:
        return "", [], {}
    anchor = max(all_ts) - timedelta(hours=ref_days_ago * 24)
    rows, movers, win = [], [], {}
    earliest = None
    for slug, pts in hist.items():
        parsed = [(dt, v) for dt, v in _pts(pts) if dt <= anchor]
        if len(parsed) < 2:
            continue
        if earliest is None or parsed[0][0] < earliest:
            earliest = parsed[0][0]
        last_dt, last = parsed[-1]
        target = last_dt - timedelta(hours=days * 24)
        past = parsed[0]
        for dt, v in parsed:
            if dt <= target:
                past = (dt, v)
            else:
                break
        span_h = (last_dt - past[0]).total_seconds() / 3600
        chg = (last - past[1]) / past[1] * 100
        if slug in MAJORS:
            rows.append((slug, last, chg, span_h))
        # в топы — только криптовалюты (фиат с редкими точками врёт),
        # стейблкоины исключаем (плоские ~0% — шум)
        if (kinds.get(slug, {}).get("category") == "Криптовалюты" and span_h >= days * 20
                and not any(x in slug for x in ("tether", "usd-coin", "trueusd", "dai", "usdc"))):
            movers.append((slug, chg, span_h))
        if slug in ("bitcoin", "ethereum", "solana"):
            win[slug] = [v for _, v in parsed[-30:]]
    want = "24 часа" if days == 1 else "7 дней"
    lines = []
    for s, v, c, sp in rows:
        tag = f"{want}" if sp >= days * 20 else f"~{sp:.0f} ч (старее нет)"
        lines.append(f"{s}: {v:.4f} USDT ({c:+.1f}% за {tag})")
    movers.sort(key=lambda x: x[1])
    head = (f"Сегодня: {date.today().isoformat()}. История с {earliest:%Y-%m-%d}. "
            f"Проценты честные: за {want}, где истории не хватило — указан реальный охват.")
    return head + "\n" + "\n".join(lines), movers, win


# ---------- команды ----------

def cmd_draft_next(args):
    topics = load_topics()
    cand = next((t for t in topics if t["status"] == "todo" and
                 (not args.lang or t["lang"] == args.lang)), None)
    if not cand:
        print("очередь пуста (или нет todo на языке)")
        return 1
    st, sim, hit = dup_check(cand["topic"], slug=cand["id"])
    print(f"тема: {cand['topic']} [{cand['lang']}] dup={st} ({sim:.2f}) {hit}")
    if st == "block":
        cand["status"] = "skipped-dup"
        save_topics(topics)
        log({"action": "skip-dup", "id": cand["id"], "hit": hit})
        print("тема-дубль — пропущена и помечена skipped-dup")
        return 2
    slug = cand["id"]
    prompt = ARTICLE_SYS.format(lang=cand["lang"], today=date.today().isoformat(),
                                slug=slug, corpus=corpus_titles())
    out = chat([{"role": "system", "content": prompt},
                {"role": "user", "content": f"Тема: {cand['topic']}"}],
               max_tokens=4000)
    if not out:
        return 1
    os.makedirs(DRAFT_DIR, exist_ok=True)
    p = os.path.join(DRAFT_DIR, f"{slug}.md")
    open(p, "w", encoding="utf-8").write(out + "\n")
    cand["status"] = "draft"
    save_topics(topics)
    log({"action": "draft", "id": cand["id"], "file": f"drafts/{slug}.md"})
    print(f"черновик → drafts/{slug}.md — дальше: dup-check, selfcheck")
    return 0


def cmd_dupcheck(args):
    raw = open(args.file, encoding="utf-8").read()
    title = (re.search(r"^title:\s*(.+)$", raw, re.M) or [None, args.file]).group(1)
    slug = (re.search(r"^slug:\s*(.+)$", raw, re.M) or [None, ""]).group(1)
    st, sim, hit = dup_check(title, raw, slug.strip(), skip=args.file)
    print(f"{st}: схожесть {sim:.2f} → {hit}")
    return 0 if st in ("ok", "warn") else 2


def selfcheck_text(raw, facts, tries=3):
    """Прогнать текст через ИИ-контролёр. True при VERDICT: PASS.

    Обрезанный вердикт (finish=length, нет 'VERDICT:') и ошибки API — повод
    повторить, а не валить язык.
    """
    import time as _t
    slugs = sorted({s for s, _, _, _ in corpus_index()})
    last = ""
    for t in range(tries):
        try:
            out = chat([{"role": "system", "content": SELFCHECK_SYS.format(
                            corpus=corpus_titles(), slugs=", ".join(slugs[:200]),
                            facts=facts or "нет (цифры запрещены)")},
                        {"role": "user", "content": raw[:6000]}],
                       max_tokens=800)
        except RuntimeError as e:
            print(f"selfcheck: попытка {t + 1} — API недоступно ({str(e)[:100]})")
            _t.sleep(15)
            continue
        if not out or "VERDICT:" not in out:
            print(f"selfcheck: попытка {t + 1} — вердикт обрезан/пуст, повторяю…")
            _t.sleep(10)
            continue
        print(out)
        return "VERDICT: PASS" in out
    print(f"selfcheck: все {tries} попытки сорваны перегрузкой — язык пропускаем")
    return False


def cmd_selfcheck_raw(raw, facts):
    return selfcheck_text(raw, facts)


def cmd_selfcheck(args):
    raw = getattr(args, "_raw", "") or open(args.file, encoding="utf-8").read()
    ok = selfcheck_text(raw, args.facts)
    log({"action": "selfcheck", "file": getattr(args, "file", ""),
         "verdict": "PASS" if ok else "FAIL"})
    return 0 if ok else 2


def cmd_publish(args):
    raw = open(args.file, encoding="utf-8").read()
    title = re.search(r"^title:\s*(.+)$", raw, re.M).group(1).strip()
    slug = re.search(r"^slug:\s*(.+)$", raw, re.M).group(1).strip()
    # ворота
    st, sim, hit = dup_check(title, raw, slug, skip=args.file)
    if st == "block":
        print(f"BLOCK: дубль ({sim:.2f}) → {hit}. Публикация отменена.")
        return 2
    if st == "warn":
        print(f"WARN: похожее ({sim:.2f}) → {hit} — продолжаю, глянь глазами.")
    langs = [l.strip() for l in args.langs.split(",")]
    src_lang = args.src_lang
    for lang in langs:
        text, t = raw, title
        if lang != src_lang:
            print(f"перевод {src_lang}→{lang}…")
            from llm_draft import TRANSLATE_SYS  # noqa
            text = chat([{"role": "system", "content": TRANSLATE_SYS.format(lang=lang)},
                         {"role": "user", "content": raw}], max_tokens=4000)
            if not text:
                return 1
            m = re.search(r"^title:\s*(.+)$", text, re.M)
            t = m.group(1).strip() if m else title
        body = text.split("---", 2)[2] if text.startswith("---") else text
        if not args.yes:
            dest = "articles/" if lang == "ru" else f"articles/{lang}/"
            print(f"[dry-run] {lang}: положил бы {dest}{slug}.md + пост в Blogger. Повтори с --yes.")
            continue
        dest = ART_DIR if (lang == "ru") else os.path.join(ART_DIR, lang)
        os.makedirs(dest, exist_ok=True)
        open(os.path.join(dest, f"{slug}.md"), "w", encoding="utf-8").write(text + "\n")
        url = create_post(lang, t, body, slug, dry=False)
        log({"action": "publish", "lang": lang, "slug": slug, "blogger": url})
    # пометить тему
    topics = load_topics()
    for t in topics:
        if t["id"] == slug or t["topic"][:30] in title:
            t["status"] = "done" if args.yes else t["status"]
    save_topics(topics)
    print("готово" + ("" if args.yes else " (сухой прогон — добавь --yes)"))
    return 0


def cmd_market(args):
    """Обзор рынка сразу на все языки — новые посты в 4 Blogger-блога (Blogger-only).

    По умолчанию БЕЗ страниц на сайте (--site включает и articles/ + ссылку).
    На каждый язык: генерация из тех же ФАКТОВ → selfcheck → (с --yes) пост в блог.
    Пауза 15с между языками — бережём free-лимиты OpenRouter.
    """
    import time as _t
    days = 1 if args.which == "daily" else 7
    period = "дневной" if days == 1 else "недельный"
    stats, movers, win = market_stats(days)
    if not stats:
        print("нет history.json — не из чего строить обзор")
        return 1
    ups = ", ".join(f"{s} {c:+.1f}%" for s, c, _ in movers[-3:][::-1])
    dns = ", ".join(f"{s} {c:+.1f}%" for s, c, _ in movers[:3])
    facts = f"{stats}\nТоп роста: {ups or 'нет данных'}\nТоп падения: {dns or 'нет данных'}"
    # ворота скуки (только daily): flat-рынок не постим — убиваем thin volume в корне
    try:
        gate = float(os.environ.get("MARKET_VOL_GATE", "3.0"))
    except ValueError:
        gate = 3.0
    #тики majors лежат в stats строками "slug: price USDT (+x.x% ...)": вытащим макс |chg|
    peak = 0.0
    for m in re.finditer(r"\(([+-][\d.,]+)%", stats):
        peak = max(peak, abs(float(m.group(1).replace(",", "."))))
    for _, c, _ in movers:
        peak = max(peak, abs(c))
    if days == 1 and peak < gate:
        print(f"рынок flat (макс. движение {peak:.1f}% < {gate:.1f}%) — постинг пропущен, thin не плодим")
        log({"action": "market-daily-skip", "peak": round(peak, 1)})
        return 0
    # вчерашний срез — серийность вместо одинаковых простыней
    y_stats, _, _ = market_stats(days, ref_days_ago=1)
    y_line = ""
    if y_stats:
        y_moves = "; ".join(y_stats.splitlines()[1:4])
        y_line = f"\nВЧЕРА В ЭТО ВРЕМЯ: {y_moves} (свяжи с сегодня: разворот/продолжение/затухание, не повторяй дословно)"
    # герой дня — мини-evergreen внутри протухающего поста (строго без дат и цифр)
    hero = movers[-1][0] if movers and movers[-1][1] > 0 else (movers[0][0] if movers else "")
    hero_line = (f"\nГЕРОЙ ДНЯ: {hero} — добавь 2-3 предложения, что это за проект "
                 f"(сеть и назначение словами; БЕЗ дат, лет, цифр и цен, "
                 f"ссылка /valuta/{hero}/)") if hero else ""
    facts += y_line  # вчерашние цифры — тоже факты для самопроверки
    # график: BTC/ETH/SOL за окно (SVG, без зависимостей)
    from charts import svg_chart  # noqa
    chart = svg_chart([(s.upper(), win[s]) for s in ("bitcoin", "ethereum", "solana") if s in win],
                      title="BTC / ETH / SOL — % от начала окна")
    # термин недели для weekly (глоссарий; модель переведёт на язык статьи)
    term_line = ""
    if days > 1:
        try:
            terms = json.load(open(os.path.join(ROOT, "glossary.json"), encoding="utf-8"))["terms"]
            term = terms[date.today().isocalendar()[1] % len(terms)]
            term_line = (f"\nТЕРМИН НЕДЕЛИ (включи раздел о нём, переведи определение "
                         f"на язык статьи, ссылка /slovar/{term['slug']}/): "
                         f"{term['slug']} | RU: {term.get('def_ru', '')} | EN: {term.get('def_en', '')}")
        except (OSError, ValueError, KeyError):
            pass
    today = date.today().isoformat()
    names = {"es": ("mercado", "Mercado"), "en": ("market", "Market"),
             "fr": ("marche", "Marché"), "ru": ("rynok", "Рынок")}
    langs = [l.strip() for l in args.langs.split(",") if l.strip() in names]
    if not langs:
        print("нет языков (es,en,fr,ru)")
        return 1
    rc_all = 0
    for i, lang in enumerate(langs):
        try:
            r = _market_lang(args, days, period, facts, y_line, hero_line, term_line,
                             chart, today, lang)
            rc_all = max(rc_all, r)
        except Exception as e:  # noqa: BLE001 — страховка (хелпер и так не бросает)
            print(f"{lang}: неожиданная ошибка ({str(e)[:150]}) — пропускаю язык")
            rc_all = 2
        if i < len(langs) - 1:
            _t.sleep(15)
    return rc_all


def _market_lang(args, days, period, facts, y_line, hero_line, term_line,
                 chart, today, lang):
    """Один язык: генерация → ворота → архив + живой пост. Возвращает 0/2. Не бросает исключений."""
    import time as _t
    names = {"es": "mercado", "en": "market", "fr": "marche", "ru": "rynok"}
    try:
        base = names[lang]
        if days == 1:
            slug = f"{base}-{today}"
            title = {"es": f"Mercado en 24 horas: {today}", "en": f"Market in 24h: {today}",
                     "fr": f"Marché en 24h : {today}", "ru": f"Рынок за сутки: {today}"}[lang]
        else:
            slug = f"{base}-semana-{today}" if lang in ("es", "fr") else (
                f"{base}-week-{today}" if lang == "en" else f"{base}-nedelya-{today}")
            title = {"es": "Mercado de la semana", "en": "Market of the week",
                     "fr": "Marché de la semaine", "ru": "Рынок за неделю"}[lang]
        prompt = MARKET_SYS.format(period=period, lang=lang, today=today, slug=slug)
        print(f"=== {lang}: генерация… ===")
        out, passed = "", False
        for g in range(2):  # вторая попытка — другим составом пула
            try:
                out = chat([{"role": "system", "content": prompt},
                            {"role": "user", "content": f"ФАКТЫ:\n{facts}{y_line}{hero_line}{term_line}\nslug: {slug}\ntitle: {title}"}],
                           max_tokens=3500)
            except RuntimeError as e:
                print(f"{lang}: генерация {g + 1} не удалась: {str(e)[:150]}")
                out = ""
            if out and selfcheck_text(out, facts):
                passed = True
                break
            print(f"{lang}: попытка {g + 1} не прошла ворота, повторяю…")
            _t.sleep(20)
        if not passed:
            print(f"{lang}: selfcheck FAIL — в блог не идёт")
            return 2
        body = out.split("---", 2)[2] if out.startswith("---") else out
        if args.site:
            dest = ART_DIR if lang == "ru" else os.path.join(ART_DIR, lang)
            if args.yes:
                os.makedirs(dest, exist_ok=True)
                open(os.path.join(dest, f"{slug}.md"), "w", encoding="utf-8").write(out + "\n")
            read_more = None  # ссылка соберётся из slug в create_post
            read_more_text = None
        else:
            # Blogger-only: честная ссылка на живую сводку (продолжения-статьи на сайте нет)
            from blogger_post import FULL_TABLE, svodka_url
            read_more = svodka_url(lang)
            read_more_text = FULL_TABLE.get(lang, FULL_TABLE["es"])
        if args.yes:
            url = create_post(lang, title, body, slug if args.site else "",
                              labels=["RateScout", period], dry=False, read_more=read_more,
                              read_more_text=read_more_text if not args.site else None,
                              extra_html=chart)
            log({"action": f"market-{args.which}", "lang": lang, "slug": slug, "blogger": url})
            # живой evergreen: тот же текст — в один URL, PATCHем каждый день (только daily)
            if days == 1 and not args.site:
                from blogger_post import upsert_live
                live_url = upsert_live(lang, body, extra_html=chart,
                                       read_more=read_more, read_more_text=read_more_text)
                log({"action": "market-live", "lang": lang, "blogger": live_url})
        else:
            from blogger_post import upsert_live
            create_post(lang, title, body, "", dry=True)
            upsert_live(lang, body, dry=True)
            print(f"[dry-run] {lang}: черновик OK, повтори с --yes для постинга")
        return 0
    except Exception as e:  # noqa: BLE001 — один язык не должен валить остальные
        print(f"{lang}: неожиданная ошибка ({str(e)[:150]}) — пропускаю язык")
        return 2


QUERY_SYS = (
    "Ты — SEO-аналитик RateScout (справочник курсов обмена криптовалют). "
    "Даны поисковые запросы пользователей и заголовки существующих статей. "
    "Верни СТРОГО JSON-массив (без пояснений, можно в ```json): "
    "[{{\"topic\": \"тема статьи\", \"lang\": \"ru|es|en\"}}], 3–10 штук. "
    "Правила: группируй похожие запросы в одну тему; мусор (бренды, навигация, "
    "одно слово) отбрось; дубли существующих статей отбрось; тема — конкретный "
    "низкочастотный вопрос (как/что/сколько/где), а не 'обзор рынка'; "
    "lang — язык запросов (кириллица→ru, иначе es, технический английский→en)."
)

QUERY_INTENT = ("обмен", "курс", "крипт", "битко", "битк", "usdt", "usdc", "btc", "eth",
                "вывод", "ввод", "кошел", "бирж", "p2p", "aml", "комис", "резерв", "спред",
                "доллар", "dolar", "cripto", "cambio", "canjear", "exchange", "wallet",
                "fee", "tasa", "retiro", "deposito", "tron", "solana", "monero", "ton")


def load_queries():
    """[(q, вес)] из yandex.json, metrika.json, queries.txt (что есть)."""
    out = []
    try:
        for x in json.load(open(os.path.join(ROOT, "yandex.json"), encoding="utf-8"))["queries"]:
            out.append((x.get("q", ""), x.get("shows") or 0))
    except (OSError, ValueError, KeyError):
        pass
    try:
        for x in json.load(open(os.path.join(ROOT, "metrika.json"), encoding="utf-8"))["phrases"]:
            out.append((x.get("q", ""), x.get("visits") or 0))
    except (OSError, ValueError, KeyError):
        pass
    try:
        for ln in open(os.path.join(ROOT, "queries.txt"), encoding="utf-8"):
            ln = ln.strip()
            if ln and not ln.startswith("#"):
                out.append((ln, 1))
    except OSError:
        pass
    return out


def _query_junk(q):
    ql = (q or "").lower().strip()
    if len(ql) < 6 or ql.startswith(("http", "www.", "/")):
        return True
    if "ratescout" in ql or "mymany" in ql or "bestchange" in ql:
        return True
    if len(ql.split()) < 2:
        return True
    return not any(k in ql for k in QUERY_INTENT)


def cmd_queries_to_topics(args):
    """НЧ-запросы → темы в topics.json (через ИИ-группировку, с антидублем)."""
    seen, cands = set(), []
    for q, w in sorted(load_queries(), key=lambda x: -x[1]):
        q = (q or "").strip()
        if not q or q.lower() in seen or _query_junk(q):
            continue
        seen.add(q.lower())
        cands.append((q, w))
    cands = cands[:args.max]
    if not cands:
        print("запросов нет (yandex.json/metrika.json/queries.txt пусты)")
        return 1
    existing = [t["topic"] for t in load_topics()] + [t for _, t, _, _ in corpus_index()[:80]]
    qlist = "\n".join(f"- {q} ({w})" for q, w in cands)
    try:
        out = chat([{"role": "system", "content": QUERY_SYS},
                    {"role": "user", "content": f"ЗАПРОСЫ (текст, вес):\n{qlist}\n\nСУЩЕСТВУЮЩИЕ:\n" +
                                                "\n".join(f"- {t}" for t in existing[:100])}],
                   max_tokens=1500)
    except RuntimeError as e:
        print(f"ИИ недоступен (free-tier перегружен): {str(e)[:120]} — попробуй позже")
        return 1
    if not out:
        return 1
    m = re.search(r"\[.*\]", out, re.S)
    try:
        items = json.loads(m.group(0)) if m else []
    except ValueError:
        print("ИИ вернул не-JSON, пропускаю")
        return 1
    topics = load_topics()
    have = {t["topic"].lower() for t in topics}
    added = 0
    for it in items:
        topic = str(it.get("topic", "")).strip()
        lang = it.get("lang", "ru") if it.get("lang") in ("ru", "es", "en") else "ru"
        if not topic or topic.lower() in have:
            continue
        st, sim, hit = dup_check(topic)
        if st == "block":
            print(f"дубль: {topic} → {hit}")
            continue
        if args.yes:
            topics.append({"id": slugify(topic)[:60] or f"q-{added}",
                           "lang": lang, "topic": topic,
                           "status": "todo", "source": "query"})
            have.add(topic.lower())
            added += 1
        print(f"[{'добавлю' if args.yes else 'кандидат'}] ({lang}) {topic}")
    if args.yes and added:
        save_topics(topics)
        log({"action": "queries-to-topics", "added": added})
    print(f"итог: {added} тем" + ("" if args.yes else " (сухой прогон — добавь --yes)"))
    return 0


def slugify(text):
    tr = {"а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
          "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
          "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
          "ф": "f", "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "shch",
          "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya"}
    text = "".join(tr.get(c, c) for c in (text or "").lower())
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:60].strip("-")


def cmd_fixup_brief(args):
    """Починить ссылку в уже опубликованном обзоре: 'Читать полностью' → 'Полная сводка → /svodka/'."""
    from blogger_post import (BLOG_IDS, CID, CSEC, RTOK, FULL_TABLE,
                              access_token, find_post, svodka_url, update_post_link)
    if not all([CID, CSEC, RTOK]):
        print("нет Blogger-секретов — сухой прогон")
        return 0
    today = date.today().isoformat()
    base = {"es": "mercado", "en": "market", "fr": "marche", "ru": "rynok"}
    titles = []
    for lang in [l.strip() for l in args.langs.split(",") if l.strip() in base]:
        titles.append((lang,
                       {"es": f"Mercado en 24 horas: {today}", "en": f"Market in 24h: {today}",
                        "fr": f"Marché en 24h : {today}", "ru": f"Рынок за сутки: {today}"}[lang]))
        titles.append((lang,
                       {"es": "Mercado de la semana", "en": "Market of the week",
                        "fr": "Marché de la semaine", "ru": "Рынок за неделю"}[lang]))
    token = access_token()
    rc = 0
    for lang, title in titles:
        blog = BLOG_IDS.get(lang, "")
        url, pid, _ = find_post(blog, token, title)
        if not pid:
            print(f"{lang}: пост '{title}' не найден — пропускаю")
            continue
        update_post_link(blog, token, pid, svodka_url(lang), FULL_TABLE.get(lang, FULL_TABLE["es"]))
        log({"action": "fixup-brief", "lang": lang, "blogger": url})
    return rc


def main():
    ap = argparse.ArgumentParser(prog="content_pipe")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("draft-next", help="следующая тема → черновик")
    d.add_argument("--lang", default="")
    sub.add_parser("dup-check", help="проверка дубля").add_argument("file")
    s = sub.add_parser("selfcheck", help="ИИ-самопроверка")
    s.add_argument("file")
    s.add_argument("--facts", default="")
    p = sub.add_parser("publish", help="публикация (ворота + Blogger)")
    p.add_argument("file")
    p.add_argument("--langs", default="es")
    p.add_argument("--src-lang", default="ru")
    p.add_argument("--yes", action="store_true")
    f = sub.add_parser("fixup-brief", help="починить ссылку в опубликованном обзоре")
    f.add_argument("--langs", default="ru")
    q = sub.add_parser("queries-to-topics", help="НЧ-запросы → темы статей")
    q.add_argument("--max", type=int, default=60)
    q.add_argument("--yes", action="store_true")
    for w in ("market-daily", "market-weekly"):
        m = sub.add_parser(w, help="ИИ-обзор рынка в 4 блога")
        m.add_argument("--langs", default="es,en,fr,ru")
        m.add_argument("--site", action="store_true",
                       help="плюс страницы на сайте в articles/ (по умолчанию Blogger-only)")
        m.add_argument("--yes", action="store_true")
    a = ap.parse_args()
    if a.cmd == "draft-next":
        return cmd_draft_next(a)
    if a.cmd == "dup-check":
        return cmd_dupcheck(a)
    if a.cmd == "selfcheck":
        return cmd_selfcheck(a)
    if a.cmd == "publish":
        return cmd_publish(a)
    if a.cmd == "fixup-brief":
        return cmd_fixup_brief(a)
    if a.cmd == "queries-to-topics":
        return cmd_queries_to_topics(a)
    if a.cmd in ("market-daily", "market-weekly"):
        a.which = "daily" if a.cmd == "market-daily" else "weekly"
        return cmd_market(a)


if __name__ == "__main__":
    sys.exit(main())
