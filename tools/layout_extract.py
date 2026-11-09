#!/usr/bin/env python3
"""Разбор оригинальной брошюры на «абзацы» с точной геометрией.

Два шага:
1. атомы (span'ы) -> визуальные строки (склейка слов выключенных строк,
   разрыв по большим зазорам и по «чипам» с рамкой);
2. строки -> абзацы (переносы с тем же кеглем, отступом и выключкой).

Результат: build/en_paras.json — для каждой страницы список абзацев
с текстом, кеглем, цветом, базовой линией и прямоугольниками атомов.
"""
import json
import os

import pymupdf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "source/BIKAI brochure2.pdf")
OUT = os.path.join(ROOT, "build/en_paras.json")

ROT = {(1.0, 0.0): 0, (0.0, -1.0): 90, (0.0, 1.0): -90, (-1.0, 0.0): 180}
BULLETS = {"u", "•", "◆", "·"}
GAP_K = 1.6  # максимальный зазор внутри одной строки, в кеглях


def atoms_of(page):
    atoms = []
    for b in page.get_text("dict")["blocks"]:
        if b["type"] != 0:
            continue
        for line in b["lines"]:
            for s in line["spans"]:
                if not s["text"].strip():
                    continue
                atoms.append({
                    "t": s["text"],
                    "size": round(s["size"], 2),
                    "color": "%06x" % s["color"],
                    "x0": round(s["bbox"][0], 1), "x1": round(s["bbox"][2], 1),
                    "y0": round(s["bbox"][1], 1), "y1": round(s["bbox"][3], 1),
                    "by": round(s["origin"][1], 1),
                    "dir": [round(v, 2) for v in line["dir"]],
                    "bold": "105_" in s["font"],
                })
    atoms.sort(key=lambda a: (a["by"], a["x0"]))
    return atoms


def chip_rects(page):
    out = []
    for dr in page.get_drawings():
        r = dr["rect"]
        if 6 < r.width < 600 and 4 < r.height < 60:
            out.append(r)
    return out


def is_chip(a, rects):
    for r in rects:
        if (r.x0 - 1 <= a["x0"] and r.y0 - 1 <= a["y0"]
                and r.x1 + 1 >= a["x1"] and r.y1 + 1 >= a["y1"]):
            if r.width * r.height < 5 * (a["x1"] - a["x0"] + 1) * (a["y1"] - a["y0"] + 1):
                return True
    return False


def build_lines(atoms, rects):
    """Группируем атомы в визуальные строки."""
    lines = []
    cur = None
    for a in atoms:
        if cur and abs(a["by"] - cur["by"]) < 0.6:
            last = cur["atoms"][-1]
            gap = a["x0"] - last["x1"]
            bullet = last["t"].strip() in BULLETS
            joinable = (a["size"] == cur["size"] and a["color"] == cur["color"]
                        and gap > -0.5 and gap < (2.5 if bullet else GAP_K) * a["size"]
                        and (bullet or last["t"].endswith(" ") or gap < 0.35 * a["size"])
                        and not is_chip(a, rects)
                        and a["t"].strip() not in BULLETS)
            if joinable:
                cur["atoms"].append(a)
                cur["x1"] = max(cur["x1"], a["x1"])
                continue
        if cur:
            lines.append(cur)
        cur = {"by": a["by"], "size": a["size"], "color": a["color"],
               "x0": a["x0"], "x1": a["x1"], "atoms": [a]}
    if cur:
        lines.append(cur)
    for l in lines:
        l["text"] = "".join(a["t"] for a in l["atoms"])
    return lines


chip_rects_cache = []


def build_paragraphs(lines):
    """Строки -> абзацы. Абзацы ведём «колонками»: строка приклеивается
    к тому открытому абзацу, который геометрически ближе всего."""
    opens = []
    for l in lines:
        size = l["size"]
        best, best_key = None, None
        bullet_line = l["atoms"][0]["t"].strip() in BULLETS
        for p in opens:
            if bullet_line or l["color"] != p["color"] or size != p["size"]:
                continue
            dy = l["by"] - p["last_by"]
            if not (1.0 * size < dy < 2.05 * size):
                continue
            indent = min(abs(l["x0"] - p["x0"]), abs(l["x0"] - p["text_x0"]))
            if indent >= 2.2 * size:
                continue
            if p["last_x1"] < l["x1"] - 0.25 * (l["x1"] - l["x0"]):
                continue
            key = (round(dy, 1), indent)
            if best_key is None or key < best_key:
                best, best_key = p, key
        if best is not None:
            best["lines"].append(l)
            best["last_by"] = l["by"]
            best["last_x1"] = l["x1"]
            best["x1"] = max(best["x1"], l["x1"])
            continue
        body = [a for a in l["atoms"] if a["t"].strip() not in BULLETS] or l["atoms"]
        opens.append({
            "by": l["by"], "size": size, "color": l["color"],
            "x0": l["x0"], "x1": l["x1"], "text_x0": body[0]["x0"],
            "bullet": l["atoms"][0]["t"].strip() in BULLETS,
            "last_by": l["by"], "last_x1": l["x1"], "lines": [l],
        })

    res = []
    for p in opens:
        atoms = [a for ln in p["lines"] for a in ln["atoms"]]
        box = None
        best_area = None
        for r in chip_rects_cache:
            if all(r.x0 - 2 <= a["x0"] and r.x1 + 2 >= a["x1"]
                   and r.y0 - 2 <= a["y0"] and r.y1 + 2 >= a["y1"] for a in atoms):
                area = r.width * r.height
                if best_area is None or area < best_area:
                    best_area, box = area, [round(r.x0, 1), round(r.y0, 1), round(r.x1, 1), round(r.y1, 1)]
        res.append({
            "text": "\n".join(ln["text"] for ln in p["lines"]),
            "flat": "".join(a["t"] for a in atoms),
            "bases": [ln["by"] for ln in p["lines"]],
            "lx0": p["lines"][0]["x0"],
            "size": p["size"], "color": p["color"],
            "x0": p["x0"], "x1": p["x1"],
            "y0": min(a["y0"] for a in atoms), "y1": max(a["y1"] for a in atoms),
            "base": p["by"], "bullet": p["bullet"], "text_x0": p["text_x0"],
            "lines": len(p["lines"]), "box": box,
            "heavy": sum(1 for a in atoms if a.get("bold")) > len(atoms) / 2,
            "rot": ROT.get(tuple(p["lines"][0]["atoms"][0].get("dir", (1, 0))), 0),
            "atoms": [{"t": a["t"], "x0": a["x0"], "y0": a["y0"],
                       "x1": a["x1"], "y1": a["y1"]} for a in atoms],
        })
    res.sort(key=lambda p: (p["base"], p["x0"]))
    return res


def main():
    doc = pymupdf.open(SRC)
    pages = []
    for i in range(doc.page_count):
        page = doc[i]
        rects = chip_rects(page)
        global chip_rects_cache
        chip_rects_cache = rects
        lines = build_lines(atoms_of(page), rects)
        paras = build_paragraphs(lines)
        seen = {}
        for pr in paras:
            key = (pr["size"], pr["text"])
            if key not in seen:
                seen[key] = "p%d#%02d" % (i + 1, len(seen) + 1)
            pr["id"] = seen[key]
        pages.append({"page": i + 1, "paras": paras})
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(pages, open(OUT, "w"), ensure_ascii=False, indent=1)
    print("абзацев:", sum(len(p["paras"]) for p in pages),
          [len(p["paras"]) for p in pages])


if __name__ == "__main__":
    main()
