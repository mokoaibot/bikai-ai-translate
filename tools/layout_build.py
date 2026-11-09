#!/usr/bin/env python3
"""Сборка варианта 2: русский текст в геометрии английского оригинала.

Берём build/en_paras.json (координаты, кегли, цвета, рамки плашек) и
tools/layout_text.py (перевод), стираем английский текст и ставим русский
в те же места: тот же левый край, та же базовая линия, тот же кегль.
Если русский длиннее — кегль аккуратно уменьшается, чтобы число строк
не изменилось (перенос 1:1 по строкам невозможен из-за длины RU).

Результат: output/BIKAI_Каталог_2026_RU_layout-original.pdf
"""
import json
import os
import re

import pymupdf

from layout_text import RU

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "source/BIKAI brochure2.pdf")
OUT = os.path.join(ROOT, "output/BIKAI_Каталог_2026_RU_layout-original.pdf")
FONT_DIR = os.path.join(ROOT, "assets/fonts")

BULLETS = {"u", "•", "◆", "·"}
MIN_SCALE = 0.68          # предел уменьшения кегля
GROW_SINGLE = 2.60        # насколько одиночной строке можно стать шире
GROW_MULTI = 1.02         # запас для многострочных абзацев

FONTS = {
    600: pymupdf.Font(fontfile=os.path.join(FONT_DIR, "Inter-600.ttf")),
    700: pymupdf.Font(fontfile=os.path.join(FONT_DIR, "Inter-700.ttf")),
}
# Абзацы оригинала, закрытые графикой (в оригинале не видны): их нельзя
# ни стирать, ни перерисовывать — они всплывут наверх.
SKIP = {"p9#19"}

def card_rects(page):
    out = []
    for dr in page.get_drawings():
        r = dr["rect"]
        if 40 < r.width < 620 and 20 < r.height < 460:
            out.append((r.x0, r.y0, r.x1, r.y1))
    return out


def card_of(p, rects):
    best, area = None, None
    for r in rects:
        if r[0] - 1 <= p["x0"] and r[1] - 1 <= p["y0"] and r[2] + 1 >= p["x1"] and r[3] + 1 >= p["y1"]:
            a = (r[2] - r[0]) * (r[3] - r[1])
            if area is None or a < area:
                best, area = r, a
    return best


VIS = {}
FILES = {600: os.path.join(FONT_DIR, "Inter-600.ttf"),
         700: os.path.join(FONT_DIR, "Inter-700.ttf")}


def rgb(hexstr):
    return tuple(int(hexstr[i:i + 2], 16) / 255 for i in (0, 2, 4))


def wrap(text, width, size, font):
    out, cur = [], ""
    for word in text.split(" "):
        trial = word if not cur else cur + " " + word
        if font.text_length(trial, size) <= width or not cur:
            cur = trial
        else:
            out.append(cur)
            cur = word
    if cur:
        out.append(cur)
    return out


def v_overlap(p, q):
    """Строки на одной высоте (а не только на одной базовой линии)."""
    return q["y0"] < p["y1"] + 0.12 * p["size"] and q["y1"] > p["y0"] - 0.12 * p["size"]


def right_obstacle(p, paras):
    lim = None
    for q in paras:
        if q is p or q["id"] == p["id"]:
            continue
        if not v_overlap(p, q) or q["text_x0"] <= p["x1"] - 0.5:
            continue
        lim = q["text_x0"] if lim is None else min(lim, q["text_x0"])
    return lim


def geom(p):
    """Возвращает (ширина, режим, центр) для абзаца."""
    if p["box"] and p["lines"] == 1:
        bx0, _, bx1, _ = p["box"]
        mode = "center" if abs((p["text_x0"] - bx0) - (bx1 - p["x1"])) < 6 else "left"
        return max(6.0, bx1 - bx0 - 4.0), mode, (bx0 + bx1) / 2

    en_w = p["x1"] - p["text_x0"]
    w = en_w * (GROW_SINGLE if p["lines"] == 1 else GROW_MULTI)

    lim = right_obstacle(p, p["_paras"])
    card = p.get("_card")
    if card:
        lim = card[2] - 6.0 if lim is None else min(lim, card[2] - 6.0)
    page_edge = p["_pw"] - 26.0
    lim = page_edge if lim is None else min(lim, page_edge)
    if lim:
        w = min(w, lim - 6.0 - p["text_x0"])
    return max(6.0, w), "left", p["text_x0"]


def changed(par, a, b, zoom, step=2, avoid=()):
    """Изменились ли пиксели абзаца между двумя рендерами.

    Так мы находим текст, который в оригинале закрыт графикой: его удаление
    не меняет картинку, и перерисовывать его нельзя — он всплывёт наверх.
    """
    x0 = int(max(0, (par["text_x0"] + 0.5) * zoom))
    x1 = int(min(a.width - 1, (par["x1"] - 0.5) * zoom))
    y0 = int(max(0, (par["y0"] + 0.5) * zoom))
    y1 = int(min(a.height - 1, (par["y1"] - 0.5) * zoom))
    if x1 <= x0 or y1 <= y0:
        return True
    sa, sb = a.samples, b.samples
    na, nb, stride = a.n, b.n, a.stride
    avoid_px = [(int(r[0] * zoom), int(r[1] * zoom), int(r[2] * zoom), int(r[3] * zoom))
                for r in avoid]
    diff = 0
    total = 0
    for y in range(y0, y1 + 1, step):
        for x in range(x0, x1 + 1, step):
            skip = False
            for ax0, ay0, ax1, ay1 in avoid_px:
                if ax0 <= x <= ax1 and ay0 <= y <= ay1:
                    skip = True
                    break
            if skip:
                continue
            ia = y * stride + x * na
            ib = y * stride + x * nb
            la = (sa[ia] * 299 + sa[ia + 1] * 587 + sa[ia + 2] * 114) // 1000
            lb = (sb[ib] * 299 + sb[ib + 1] * 587 + sb[ib + 2] * 114) // 1000
            diff += abs(la - lb)
            total += 1
    return total > 0 and diff / total > 1.2


def visible_mask(doc, zoom=2.0):
    """Рендеры оригинала — для сравнения «до/после удаления текста»."""
    out = {}
    for pno in range(doc.page_count):
        out[pno] = (doc[pno].get_pixmap(matrix=pymupdf.Matrix(zoom, zoom)), zoom)
    return out


def line_step(p):
    bases = p["bases"]
    if len(bases) > 1:
        return (bases[-1] - bases[0]) / (len(bases) - 1)
    return p["size"] * 1.42


def paragraphs_below(p, paras):
    ys = []
    for q in paras:
        if q is p or q["y0"] <= p["base"] + 1:
            continue
        if q["x1"] < p["text_x0"] - 1 or q["x0"] > p["x1"] + 1:
            continue
        ys.append(q["y0"])
    return min(ys) if ys else None


def fit(p, text, font):
    """Подбор кегля и разбиение на строки."""
    if p["rot"]:
        width = (p["y1"] - p["y0"]) * 1.12
        blocks = text.split("\n")
        size = p["size"]
        lines = []
        for _ in range(90):
            lines = []
            for b in blocks:
                lines += wrap(b, width, size, font)
            if (len(lines) == 1 and font.text_length(lines[0], size) <= width + 0.2) \
                    or size <= p["size"] * MIN_SCALE:
                return size, lines
            size = round(size * 0.99, 2)
        return size, lines
    width = p["_geo"][0]
    step = line_step(p)
    limit = paragraphs_below(p, p["_paras"])
    slots = p["lines"]

    blocks = text.split("\n")
    if p["lines"] == 1:
        slots = 1
    size = p["size"]
    lines = []
    for _ in range(90):
        lines = []
        for b in blocks:
            lines += wrap(b, width, size, font)
        widest = max(font.text_length(l, size) for l in lines) if lines else 0
        ok = len(lines) <= slots and widest <= width + 0.2
        if ok or size <= p["size"] * MIN_SCALE:
            return size, lines
        size = round(size * 0.99, 2)
    return size, lines


def draw_page(doc, pg):
    page = doc[pg["page"] - 1]
    paras = pg["paras"]
    rects = card_rects(page)
    pw = page.rect.width
    todo = []
    for p in paras:
        if p["id"] not in RU or p["id"] in SKIP:
            continue
        p = dict(p)
        p["_paras"] = paras
        p["_card"] = card_of(p, rects)
        p["_pw"] = pw
        p["_geo"] = geom(p)
        todo.append(p)

    # 1. стираем английский текст
    for p in todo:
        for a in p["atoms"]:
            r = pymupdf.Rect(a["x0"] - 0.7, a["y0"] - 0.7, a["x1"] + 0.7, a["y1"] + 0.9)
            page.add_redact_annot(r)
    if todo:
        page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE,
                              graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
                              text=pymupdf.PDF_REDACT_TEXT_REMOVE)

    before, zoom = VIS[pg["page"] - 1]
    after = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))

    def others(p):
        out = []
        for q in todo:
            if q is p:
                continue
            for a in q["atoms"]:
                out.append((a["x0"] - 1.2, a["y0"] - 1.2, a["x1"] + 1.2, a["y1"] + 1.2))
        return out

    todo = [p for p in todo if changed(p, before, after, zoom, avoid=others(p))]

    # 1b. PyMuPDF удаляет текст целыми текстовыми объектами: рядом с
    # переведённой строкой могут пропасть непереведённые. Возвращаем их.
    flat = re.sub(r"\s+", "", page.get_text("text"))
    for p in paras:
        if p["id"] in RU or p["id"] in SKIP:
            continue
        if not changed(p, before, after, zoom, avoid=others(p)):
            continue
        if re.sub(r"\s+", "", p["flat"]) in flat:
            continue
        redraw_original(page, p)

    # 2. ставим русский текст
    fits = []
    for p in todo:
        font = FONTS[700 if p["heavy"] else 600]
        text = RU[p["id"]]
        if p["bullet"] and text[:1] in BULLETS:
            text = text[1:].lstrip()
        size, lines = fit(p, text, font)
        fits.append([p, font, text, size, lines])

    # выравниваем кегли одиночных плашек в пределах одной базовой линии
    mins = {}
    for p, font, text, size, lines in fits:
        if p["lines"] == 1 and p["box"] and not p["rot"]:
            k = (p["base"] // 2)
            mins[k] = min(mins.get(k, 99), size)
    for row in fits:
        p, font, text, size, lines = row
        if p["lines"] == 1 and p["box"] and not p["rot"]:
            k = (p["base"] // 2)
            if size > mins[k] + 0.01:
                size = mins[k]
                lines = []
                for b in text.split("\n"):
                    lines += wrap(b, p["_geo"][0], size, font)
                row[3], row[4] = size, lines

    for p, font, text, size, lines in fits:

        if p["rot"]:
            draw_rotated(page, p, text, size, font)
            continue

        width, mode, anchor = p["_geo"]
        x = p["text_x0"]
        centered = mode == "center"
        step = line_step(p) if p["lines"] > 1 else size * 1.30
        step = max(step, size * 1.06)
        tw = pymupdf.TextWriter(page.rect)
        for i, ln in enumerate(lines):
            w = font.text_length(ln, size)
            lx = x
            if centered:
                lx = anchor - w / 2
            tw.append((lx, p["base"] + i * step), ln, font=font, fontsize=size)
        if tw.text_rect is not None:
            tw.write_text(page, color=rgb(p["color"]))

        # маркер списка
        if p["bullet"]:
            batom = None
            for a in p["atoms"]:
                if a["t"].strip() in BULLETS and a["x0"] < p["text_x0"] - 0.5:
                    batom = a
                    break
            if batom:
                bfont = FONTS[600]
                bsize = p["size"] * 0.62
                btw = pymupdf.TextWriter(page.rect)
                btw.append((batom["x0"], p["base"]), "◆", font=bfont, fontsize=bsize)
                btw.write_text(page, color=rgb(p["color"]))


def redraw_original(page, p):
    """Возвращает на место непереведённый текст, стёртый редакцией."""
    font = FONTS[700 if p["heavy"] else 600]
    tw = pymupdf.TextWriter(page.rect)
    for base, line in zip(p["bases"], p["text"].split("\n")):
        if not line.strip():
            continue
        tw.append((p["text_x0"], base), line, font=font, fontsize=p["size"])
    if tw.text_rect is not None:
        tw.write_text(page, color=rgb(p["color"]))


def draw_rotated(page, p, text, size, font):
    """Повёрнутые надписи (CONTENTS, подписи осей)."""
    color = rgb(p["color"])
    x0, y0, x1, y1 = p["x0"], p["y0"], p["x1"], p["y1"]
    if p["rot"] == -90:      # текст читается сверху вниз
        point = (x0 + size * 0.78, y0)
        rot = 270
    else:                    # rot == 90, читается снизу вверх
        point = (x1 - size * 0.22, y1)
        rot = 90
    page.insert_text(point, text, fontname="inter", fontfile=FILES[600 if not p["heavy"] else 700],
                     fontsize=size, color=color, rotate=rot)


def main():
    data = json.load(open(os.path.join(ROOT, "build/en_paras.json"), encoding="utf-8"))
    doc = pymupdf.open(SRC)
    global VIS
    VIS = visible_mask(doc)
    for pg in data:
        draw_page(doc, pg)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    doc.subset_fonts()
    doc.save(OUT, garbage=4, deflate=True)
    print("saved", OUT, "pages", doc.page_count, os.path.getsize(OUT) // 1024, "KB")


if __name__ == "__main__":
    main()
