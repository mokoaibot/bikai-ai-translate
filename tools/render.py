#!/usr/bin/env python3
"""Вёрстка PDF-каталога BIKAI (RU) по шаблону оригинальной брошюры.

Вход:  build/content.json + assets/ (шрифты, логотип, обложка, рисунки)
Выход: build/catalog.html, output/BIKAI_Каталог_2026_RU.pdf
"""
import html
import json
import os
import re

from PIL import Image
from weasyprint import HTML

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

data = json.load(open("build/content.json", encoding="utf-8"))
CSS_TEXT = open("tools/style.css", encoding="utf-8").read()
DENSE = json.load(open("build/density.json", encoding="utf-8")) if os.path.exists("build/density.json") else {}

OS_ACR = {"УФ", "ИК", "ГХ", "ЖХ", "ВЭЖХ", "МС", "ПАУ", "ОСКО", "ПФ", "ТФЭ", "НРИУ",
          "МКРИУ", "В", "Г", "Ш", "ПК", "ПО", "ЕФ", "ПТФЭ", "ПА", "ЖК"}


def esc(t):
    return html.escape(t, quote=False)


def sentence_case(text: str) -> str:
    """'УФ-ВИДИМЫЙ ДЕТЕКТОР' -> 'УФ-видимый детектор'; латиница и аббревиатуры сохраняются."""
    words = re.findall(r"[\w\-]+|[^\w\-]+", text, re.UNICODE)
    out, first = [], True
    for w in words:
        if not re.match(r"[\w\-]", w, re.UNICODE):
            out.append(w)
            continue
        parts = []
        for part in w.split("-"):
            if (re.fullmatch(r"[\x20-\x7F]+", part)
                    or re.search(r"\d", part)
                    or part.upper() in OS_ACR):
                parts.append(part)
            elif first:
                parts.append(part[:1].upper() + part[1:].lower())
            else:
                parts.append(part.lower())
            first = False
        out.append("-".join(parts))
    return "".join(out)


# ------------------------------------------------------------------ главы
CHKEY = {
    "Компания и контакты": "00",
    "Серии BIKAI-1511/1521 Pro — выбор конфигурации для жидкостной хроматографии": "01",
    "Масс-детектор серии MSD 9000": "02", "Масс-детектор серии MSD 8000": "02",
    "Генератор азота серии LIGHT": "03",
    "Насос": "04", "Автосэмплер": "04", "Термостат колонок": "04",
    "УФ-видимый детектор (UV-Vis)": "04", "Диодноматричный детектор (DAD)": "04",
    "Флуоресцентный детектор": "04", "Рефрактометрический детектор": "04",
    "Испарительный детектор светорассеяния (ELSD)": "04", "Детектор заряженного аэрозоля (CAD)": "04",
    "Коллектор фракций (автоматическое управление)": "05",
    "Коллектор фракций (ручное управление)": "05", "ГХ-автосэмплер": "05",
    "Рабочая станция ChromCore": "06", "Типовые применения": "07",
}

KICKERS = {
    "Компания и контакты": "00  Компания / Контакты",
    "Серии BIKAI-1511/1521 Pro — выбор конфигурации для жидкостной хроматографии":
        "01  Хроматография / Жидкостная хроматография",
    "Масс-детектор серии MSD 9000": "02  Масс-спектрометрия / MSD 9000",
    "Масс-детектор серии MSD 8000": "02  Масс-спектрометрия / MSD 8000",
    "Генератор азота серии LIGHT": "03  Генерация азота / Серия LIGHT",
    "Насос": "04  Модули ЖХ / Насосы",
    "Автосэмплер": "04  Модули ЖХ / Автосэмплеры",
    "Термостат колонок": "04  Модули ЖХ / Термостаты колонок",
    "УФ-видимый детектор (UV-Vis)": "04  Детекторы / УФ-видимый",
    "Диодноматричный детектор (DAD)": "04  Детекторы / Диодноматричный",
    "Флуоресцентный детектор": "04  Детекторы / Флуоресцентный",
    "Рефрактометрический детектор": "04  Детекторы / Рефрактометрический",
    "Испарительный детектор светорассеяния (ELSD)": "04  Детекторы / ELSD",
    "Детектор заряженного аэрозоля (CAD)": "04  Детекторы / CAD",
    "Коллектор фракций (автоматическое управление)": "05  Сбор фракций / Автоматический коллектор",
    "Коллектор фракций (ручное управление)": "05  Сбор фракций / Ручной коллектор",
    "ГХ-автосэмплер": "05  Сбор фракций / ГХ-автосэмплер",
    "Рабочая станция ChromCore": "06  Программное обеспечение / ChromCore",
    "Типовые применения": "07  Типовые применения",
}

CHAPTERS = [
    ("ch00", "00", "Компания и контакты", "Офисы в Китае и Японии · контакты"),
    ("ch01", "01", "Жидкостная хроматография", "1511 Pro HPLC · 1521 Pro UHPLC · конфигурации"),
    ("ch02", "02", "Масс-детекторы MSD 9000 / MSD 8000", "Тройной квадруполь · одиночный квадруполь"),
    ("ch03", "03", "Генератор азота серии LIGHT", "LIGHT2 · LIGHT3 · LIGHT3 Pro · совместимость с МС"),
    ("ch04", "04", "Модули и детекторы ВЭЖХ", "Насосы · автосэмплеры · термостаты · 6 типов детекторов"),
    ("ch05", "05", "Сбор фракций и ГХ-автосэмплер", "Автоматический и ручной коллекторы · пробоотбор ГХ"),
    ("ch06", "06", "Рабочая станция ChromCore", "21 CFR Part 11 · GMP/GLP · IQ/OQ/PQ"),
    ("ch07", "07", "Типовые применения", "Семаглутид · ПАУ в воде · молочная смесь · яд змеи"),
    ("appA", "A", "Приложение А. Расшифровка надписей на рисунках", "Двуязычный глоссарий к рисункам"),
    ("appB", "Б", "Приложение Б. Примечания переводчика", "Технические примечания к исходному макету"),
]

TITLE_OVERRIDE = {
    "Серии BIKAI-1511/1521 Pro — выбор конфигурации для жидкостной хроматографии":
        ("Жидкостная хроматография", "Серии BIKAI-1511/1521 Pro — выбор конфигурации"),
}

FIG_DIR = "assets/figures"


def fig_geometry(src):
    try:
        with Image.open(src) as im:
            w, h = im.size
        return "portrait" if h > w else "landscape"
    except Exception:
        return "landscape"


# ------------------------------------------------------------------ разбор
def split_sections(blocks):
    front, sections, cur, started = [], [], None, False
    for b in blocks:
        if b["t"] == "h1":
            started = True
            continue
        if not started:
            continue
        if b["t"] == "h2":
            cur = {"title": b["text"], "blocks": []}
            sections.append(cur)
            continue
        (front if cur is None else cur["blocks"]).append(b)
    return front, sections


front, sections = split_sections(data["blocks"])

# ------------------------------------------------------------------ рендер блоков
note_no = []


def render_table(b):
    rows = [list(r) for r in b["rows"]]
    ncol = max(len(r) for r in rows)
    for r in rows:
        r += [""] * (ncol - len(r))
    # эмуляция вертикального объединения в первом столбце
    for i in range(1, len(rows)):
        if not rows[i][0] and rows[i - 1][0]:
            rows[i][0] = rows[i - 1][0]
    head, body = rows[0], rows[1:]
    ths = "".join(f"<th>{esc(c)}</th>" for c in head)
    trs = "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in r) + "</tr>" for r in body)
    cls = ("spec wide" if ncol >= 4 else "spec") + (" keep" if len(rows) <= 16 else " long")
    return f'<table class="{cls}"><thead><tr>{ths}</tr></thead><tbody>{trs}</tbody></table>'


def render_fig(b, big_fig=False):
    if not b.get("fig_no"):
        return ""
    geo = fig_geometry(b["src"])
    cls = "figcard " + geo + (" big" if big_fig else "")
    cap = sentence_case(b["caption"] or "").replace("ПОДПИСЬ В ИСХОДНИКЕ", "в оригинале")
    return (f'<figure class="{cls}"><img src="{b["src"]}" alt="">'
            f'<figcaption><b>Рисунок {b["fig_no"]}.</b> {esc(cap)}</figcaption></figure>')


def render_blocks(bs, big_fig=False):
    out = []
    i = 0
    while i < len(bs):
        b = bs[i]
        t = b["t"]
        if t == "h3":
            # заголовок держим вместе со следующим рисунком/таблицей
            nxt = bs[i + 1] if i + 1 < len(bs) else None
            if nxt is not None and (nxt["t"] == "fig" or
                                    (nxt["t"] == "table" and len(nxt["rows"]) <= 16)):
                inner = render_fig(nxt, big_fig) if nxt["t"] == "fig" else render_table(nxt)
                out.append(f'<div class="keepblock"><h3>{esc(b["text"])}</h3>{inner}</div>')
                i += 2
                continue
            out.append(f'<h3>{esc(b["text"])}</h3>')
        elif t == "p":
            out.append(f"<p>{esc(b['text'])}</p>")
        elif t == "ul":
            out.append("<ul>" + "".join(f"<li>{esc(x)}</li>" for x in b["items"]) + "</ul>")
        elif t == "table":
            out.append(render_table(b))
        elif t == "fig":
            out.append(render_fig(b, big_fig))
        elif t == "note":
            note_no.append(b["text"])
            out.append(f'<p class="noteref">См. примечание {len(note_no)} в Приложении Б.</p>')
        i += 1
    return "\n".join(out)


def is_sparse(bs):
    text = sum(len(b.get("text", "")) + sum(len(i) for i in b.get("items", [])) for b in bs)
    figs = sum(1 for b in bs if b["t"] == "fig")
    return not any(b["t"] == "table" for b in bs) and figs <= 1 and text < 420
    return not any(b["t"] == "table" for b in bs) and figs <= 1 and text < 420


# ------------------------------------------------------------------ HTML
H = []
A = H.append
A("<!DOCTYPE html><html lang='ru'><head><meta charset='utf-8'>"
  "<title>BIKAI — Полный каталог 2026 (RU)</title>"
  f"<style>{CSS_TEXT}</style></head><body>")

# --- обложка
A("""
<section class="cover">
  <img class="logo" src="assets/img/logo_bikai.png" alt="BIKAI">
  <div class="tag">Build Innovation · Keep Accuracy Intact</div>
  <div class="ptitle">ПОЛНЫЙ КАТАЛОГ 2026</div>
  <div class="prule"></div>
  <div class="ptag">ПРЕЦИЗИОННЫЙ АНАЛИЗ<br>ДЛЯ ЛУЧШЕГО БУДУЩЕГО</div>
  <div class="band"></div>
  <img class="hero" src="assets/img/cover_hero.png" alt="">
</section>
""")

# --- идентификаторы секций и якоря глав
sec_ids = {}
chapter_anchor = {}
for i, sec in enumerate(sections):
    key = CHKEY.get(sec["title"], "x")
    sid = f"ch{key}-{i}"
    sec_ids[i] = sid
    chapter_anchor.setdefault(key, sid)
chapter_anchor["A"] = "appA"
chapter_anchor["Б"] = "appB"

# --- оглавление
pills = "".join(
    f'<a class="pill" href="#{chapter_anchor.get(n, a)}"><span class="pn">{n}</span>'
    f'<span class="ptxt"><b>{esc(t)}</b><i>{esc(s)}</i></span></a>'
    for a, n, t, s in CHAPTERS)

A(f"""
<section class="tocpage">
  <div class="tochead">
    <h1 class="toctitle">Каталог BIKAI</h1>
    <p class="tocsub">Аналитические приборы и конфигурации. Полное издание 2026 года на русском языке.</p>
  </div>
  <div class="tocband">
    <div class="vlabel">СОДЕРЖАНИЕ</div>
    <div class="pills">{pills}</div>
  </div>
</section>
""")

# --- вступительная страница
A('<section class="product" id="intro">'
  '<div class="kick">BIKAI / Полный каталог 2026</div>'
  '<h1 class="long">Полный каталог аналитических приборов BIKAI 2026</h1>'
  '<p class="lead">Руководство по конфигурации · полное издание</p>')
intro_paras = [b["text"] for b in front if b["t"] == "p"]
if intro_paras:
    A(f'<p class="tagline">{esc(intro_paras[0])}</p>')
    for p in intro_paras[1:]:
        A(f'<p class="big">{esc(p)}</p>')
A("""
<div class="kpis">
  <div class="kpi"><span>1511 Pro / 1521 Pro</span><b>ВЭЖХ · УВЭЖХ</b><i>до 22 000 psi</i></div>
  <div class="kpi"><span>MSD 9000 / 8000</span><b>МС/МС · МС</b><i>тройной квадруполь</i></div>
  <div class="kpi"><span>Серия LIGHT</span><b>N₂ / воздух</b><i>до 35 л/мин</i></div>
  <div class="kpi"><span>ChromCore</span><b>21 CFR Part 11</b><i>IQ / OQ / PQ</i></div>
</div>
<div class="trio">
  <div class="tcell"><img src="assets/figures/fig02.png" alt=""><span>1511 Pro HPLC</span></div>
  <div class="tcell"><img src="assets/figures/fig04.png" alt=""><span>MSD 9000</span></div>
  <div class="tcell"><img src="assets/figures/fig06.png" alt=""><span>Серия LIGHT</span></div>
</div>
<div class="intro-foot">
  <div class="if-item"><b>8 разделов</b><i>от жидкостной хроматографии до типовых применений</i></div>
  <div class="if-item"><b>29 рисунков</b><i>приборы, схемы и хроматограммы</i></div>
  <div class="if-item"><b>26 таблиц</b><i>технические характеристики и конфигурации</i></div>
</div>
</section>
""")

# --- секции
for i, sec in enumerate(sections):
    title = sec["title"]
    kicker = KICKERS.get(title, "BIKAI / Каталог")
    bs = list(sec["blocks"])
    lead = None
    if bs and bs[0]["t"] == "p":
        lead = bs.pop(0)["text"]
    if title in TITLE_OVERRIDE:
        title, lead = TITLE_OVERRIDE[title]
    sparse = is_sparse(bs)

    if title == "Компания и контакты":
        texts = [b["text"] for b in bs if b["t"] == "p"]
        lvl0 = DENSE.get(str(i), 0)
        A(f'<section class="product{" dense%d" % lvl0 if lvl0 else ""}" id="{sec_ids[i]}"><div class="kick">{esc(kicker)}</div>'
          f'<h1>Компания и контакты</h1><p class="lead">{esc(lead or "")}</p>')
        cards = [
            ("Штаб-квартира", "BIKAI Technology (Сучжоу) Co., LTD",
             ["2-B702, улица Даоань, Сучжоу, Китай",
              "info@uvtech-cc.com", "+86 186 1336 5565"]),
            ("Офис в Китае", "Пекинская компания UVTech Inc.",
             ["2-й этаж, корпус 3, № 1 Чаоцянь Роуд", "Пекин, Китай"]),
            ("Офис в Японии", "BIKAI Technology Co., Ltd.",
             ["Акихабара, здание 2, этаж 2", "1-11 Канда Идзуми-чо, Тиёда-ку", "Токио, Япония"]),
        ]
        A('<div class="contacts">')
        for cap, name, lines in cards:
            A(f'<div class="ccard"><span class="ccap">{esc(cap)}</span><b>{esc(name)}</b>'
              + "".join(f"<i>{esc(l)}</i>" for l in lines) + "</div>")
        A("</div>")
        A('<div class="contact-note"><b>По вопросам конфигурации и поставки.</b> '
          'Напишите нам — инженеры BIKAI помогут подобрать состав системы под вашу методику: '
          'модули, детекторы, колонки и расходные материалы.</div>')
        A('<div class="photo-band"><img src="assets/img/cover_hero.png" alt=""></div>')
        A("</section>")
        continue

    lvl = DENSE.get(str(i), 0)
    dcls = f" dense{lvl}" if lvl else ""
    A(f'<section class="product{dcls}" id="{sec_ids[i]}">'
      f'<div class="kick">{esc(kicker)}</div>')
    hcls = ' class="long"' if len(title) > 34 else ""
    A(f"<h1{hcls}>{esc(title)}</h1>")
    if lead:
        A(f'<p class="lead">{esc(lead)}</p>')
    A(render_blocks(bs, big_fig=sparse))
    A("</section>")

# --- приложение А
A('<section class="product" id="appA"><div class="kick">Приложение А / Расшифровка надписей на рисунках</div>'
  '<h1 class="long">Приложение А. Расшифровка надписей на рисунках</h1>'
  '<p class="lead">Двуязычный глоссарий: как читаются надписи на иллюстрациях и в интерфейсах</p>'
  '<p>Рисунки в каталоге сохранены в исходном виде, поэтому часть подписей на них приведена '
  'на английском языке. Ниже — построчный перевод всех надписей с привязкой к номеру рисунка.</p>')
for g in data["glossary"]:
    rows = g["rows"]
    ths = "".join(f"<th>{esc(c)}</th>" for c in rows[0])
    trs = "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in r) + "</tr>" for r in rows[1:])
    title = f"Рисунок {g['fig_no']}" if g["fig_no"] else "Надписи"
    A(f'<h3>{title}</h3><table class="spec gloss"><thead><tr>{ths}</tr></thead><tbody>{trs}</tbody></table>')
A("</section>")

# --- приложение Б
A('<section class="product" id="appB"><div class="kick">Приложение Б / Примечания переводчика</div>'
  '<h1 class="long">Приложение Б. Примечания переводчика</h1>'
  '<p class="lead">Технические замечания к исходному макету и терминологии</p><ol class="notes">')
for n in data["notes"]:
    A(f"<li>{esc(n)}</li>")
A("</ol></section></body></html>")

HTML_DOC = "\n".join(H)
os.makedirs("build", exist_ok=True)
open("build/catalog.html", "w", encoding="utf-8").write(HTML_DOC)

OUT = os.environ.get("OUT_PDF", "output/BIKAI_Каталог_2026_RU.pdf")
os.makedirs("output", exist_ok=True)
doc = HTML(string=HTML_DOC, base_url=ROOT + "/").render()
anchors = {}
for pno, page in enumerate(doc.pages, 1):
    for a in page.anchors:
        anchors.setdefault(a, pno)
json.dump(anchors, open("build/anchors.json", "w"), indent=1)
doc.write_pdf(OUT)
print("html:", len(HTML_DOC), "| sections:", len(sections), "| pages:", len(doc.pages),
      "| pdf KB:", os.path.getsize(OUT) // 1024)
