#!/usr/bin/env python3
"""Извлекает структуру и рисунки из DOCX-перевода в content.json + assets/figures/."""
import json
import os
import re
import docx
from docx.table import Table
from docx.text.paragraph import Paragraph
from docx.oxml.ns import qn

SRC = "source/Полный каталог BIKAI 2026 — аналитические приборы (RU, чистовой перевод).docx"
OUT_JSON = "build/content.json"
FIG_DIR = "assets/figures"

os.makedirs(FIG_DIR, exist_ok=True)
doc = docx.Document(SRC)
body = doc.element.body

blocks = []          # основной поток
notes = []           # примечания переводчика
glossary = []        # таблицы "Текст на картинке | Перевод"
figures = []         # все рисунки (для нумерации)
_fig_counter = 0
_last_blobs = []     # картинки текущего абзаца
pending_img = []     # блоки figure без подписи


def para_text(p):
    return re.sub(r"\s+", " ", p.text).strip()


def save_image(blob, ext, idx):
    path = f"{FIG_DIR}/fig{idx:02d}.{ext}"
    with open(path, "wb") as f:
        f.write(blob)
    return path


def paragraph_images(p):
    """Возвращает список (blob, ext) для картинок внутри абзаца."""
    out = []
    blips = p._p.xpath(".//a:blip")
    for blip in blips:
        rid = blip.get(qn("r:embed"))
        if not rid:
            continue
        part = doc.part.related_parts.get(rid)
        if part is None:
            continue
        ext = os.path.splitext(str(part.partname))[1].lstrip(".").lower() or "png"
        if ext not in ("png", "jpg", "jpeg", "emf", "wmf", "gif", "bmp"):
            ext = "png"
        out.append((part.blob, ext))
    return out


CAP_RE = re.compile(r"^РИСУНОК\s+(\d+)\s*[—\-–]\s*(.+)$", re.S)


def handle_para(p):
    global _fig_counter
    style = p.style.name
    text = para_text(p)

    # картинки внутри абзаца
    for blob, ext in paragraph_images(p):
        _fig_counter += 1
        path = save_image(blob, ext, _fig_counter)
        fig = {"t": "fig", "src": path, "fig_no": None, "caption": None}
        blocks.append(fig)
        figures.append(fig)
        pending_img.append(fig)

    if not text:
        return

    m = CAP_RE.match(text)
    if m:
        no, cap = m.group(1), m.group(2).strip()
        target = pending_img[-1] if pending_img else None
        if target is not None:
            target["fig_no"] = no
            target["caption"] = cap
            pending_img.clear()
        else:
            blocks.append({"t": "figcap", "fig_no": no, "caption": cap})
        return

    if text in ("---", "--", "—"):
        blocks.append({"t": "sep"})
        return

    if style.startswith("toc"):
        return  # оглавление собираем сами

    if style == "Heading 1":
        blocks.append({"t": "h1", "text": text})
        return
    if style == "Heading 2":
        blocks.append({"t": "h2", "text": text})
        return
    if style == "Heading 3":
        blocks.append({"t": "h3", "text": text})
        return
    if style == "List Bullet":
        blocks.append({"t": "li", "text": text.rstrip(" .;,") + ";"})
        return

    if text.lower().startswith("примечание"):
        notes.append(text)
        blocks.append({"t": "note", "text": text})
        return

    blocks.append({"t": "p", "text": text})


def handle_table(tb):
    rows = []
    for r in tb.rows:
        cells, seen = [], set()
        for c in r.cells:
            if id(c._tc) in seen:
                continue
            seen.add(id(c._tc))
            cells.append(re.sub(r"\s+", " ", c.text).strip())
        rows.append(cells)
    if not rows:
        return
    head = " ".join(rows[0]).lower()
    if "текст на картинке" in head:
        fig_no = None
        for b in reversed(blocks):
            if b["t"] == "fig" and b.get("fig_no"):
                fig_no = b["fig_no"]
                break
            if b["t"] in ("h2", "h3"):
                break
        glossary.append({"fig_no": fig_no, "rows": rows})
    else:
        blocks.append({"t": "table", "rows": rows})


for child in body.iterchildren():
    if child.tag == qn("w:p"):
        handle_para(Paragraph(child, doc))
    elif child.tag == qn("w:tbl"):
        handle_table(Table(child, doc))

# склеиваем подряд идущие li в списки
merged = []
for b in blocks:
    if b["t"] == "li" and merged and merged[-1]["t"] == "ul":
        merged[-1]["items"].append(b["text"])
    elif b["t"] == "li":
        merged.append({"t": "ul", "items": [b["text"]]})
    else:
        merged.append(b)

data = {"blocks": merged, "notes": notes, "glossary": glossary,
        "figures": [{"src": f["src"], "fig_no": f["fig_no"], "caption": f["caption"]} for f in figures]}
with open(OUT_JSON, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=1)

print("blocks:", len(merged), "figures:", len(figures), "notes:", len(notes), "glossary:", len(glossary))
from collections import Counter
print(Counter(b["t"] for b in merged))
print("рисунки:", [(f["fig_no"], f["src"]) for f in figures][:5], "...")
missing = [f["src"] for f in figures if not f["fig_no"]]
print("без подписи:", missing)
