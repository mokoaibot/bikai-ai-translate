#!/usr/bin/env python3
"""Авто-подгонка плотности: уменьшает рисунки/таблицы в «хвостах» разделов.

Итеративно рендерит PDF, измеряет заполненность последней страницы каждого
раздела и повышает уровень плотности (dense1 → dense2) там, где раздел
занимает 2+ страницы, а последняя заполнена меньше чем на 42 %.
"""
import json
import os
import subprocess
import sys

import pymupdf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

TMP = "build/fit_tmp.pdf"
DENSITY = "build/density.json"
THRESHOLD = 44        # % заполнения «хвоста»
MAX_LEVEL = 2
ITERATIONS = 4


def render():
    env = dict(os.environ, OUT_PDF=TMP)
    subprocess.run([sys.executable, "tools/render.py"], check=True, env=env,
                   stdout=subprocess.DEVNULL)
    anchors = json.load(open("build/anchors.json"))
    doc = pymupdf.open(TMP)
    return anchors, doc


def fill_pct(page):
    ys = []
    for b in page.get_text("blocks"):
        if not b[4].strip() or b[1] > 758 or b[3] < 60:
            continue
        ys.append(b[3])
    for im in page.get_image_info():
        r = im["bbox"]
        if r[3] < 758:
            ys.append(r[3])
    for dr in page.get_drawings():
        if dr["rect"].y1 < 758:
            ys.append(dr["rect"].y1)
    return round(max(ys or [0]) / 825 * 100)


def section_spans(anchors, npages):
    items = sorted(anchors.items(), key=lambda kv: kv[1])
    spans = {}
    for i, (sid, start) in enumerate(items):
        end = items[i + 1][1] - 1 if i + 1 < len(items) else npages
        if sid in ("intro", "appA", "appB"):
            continue
        spans[sid] = (start, max(start, end))
    return spans


def main():
    density = json.load(open(DENSITY)) if os.path.exists(DENSITY) else {}
    best = None
    for it in range(ITERATIONS):
        json.dump(density, open(DENSITY, "w"), indent=1)
        anchors, doc = render()
        spans = section_spans(anchors, doc.page_count)
        # сопоставляем id раздела с его индексом (id имеет вид chKK-i)
        changed = 0
        report = []
        for sid, (s, e) in spans.items():
            tail = fill_pct(doc[e - 1])
            idx = sid.split("-")[-1] if "-" in sid else None
            if idx is None or not idx.isdigit():
                continue
            idx = str(int(idx))
            lvl = density.get(idx, 0)
            pages = e - s + 1
            report.append((sid, pages, tail, lvl))
            if pages >= 2 and tail < THRESHOLD and lvl < MAX_LEVEL:
                density[idx] = lvl + 1
                changed += 1
        npages = doc.page_count
        print(f"итерация {it+1}: страниц {npages}, подтянуто разделов {changed}")
        print("   " + "; ".join(f"{s}:{p}стр/{t}%/L{l}" for s, p, t, l in report))
        if best is None or npages < best[0]:
            best = (npages, dict(density))
        doc.close()
        if not changed:
            break
    final = best[1] if best else density
    json.dump(final, open(DENSITY, "w"), indent=1)
    print("итог: страниц", best[0] if best else "?", "| density:", best[1] if best else density)


if __name__ == "__main__":
    main()
