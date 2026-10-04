#!/usr/bin/env python3
"""
مقابلة نسخ رسالة «التبتل» آليًا بـ CollateX.

المدخلات: transcriptions/<الرمز>/*.txt  (تُقرأ مرتّبة بالاسم وتُدمج نصًّا واحدًا لكل نسخة)
المخرجات: collation/out/
    - table.txt        جدول المحاذاة كاملًا
    - variants.csv     الفروق وحدها (موضع الخلاف وقراءة كل نسخة) — مسودة الحواشي
    - apparatus.xml    الفروق بصيغة TEI (app / rdg) جاهزة للدمج في tei/

التطبيع: تُقارَن الكلمات بعد حذف التشكيل والتطويل وتوحيد الألف والياء والتاء المربوطة،
مع بقاء الرسم الأصلي في المخرجات؛ فلا تُعدّ «إلى/الى» أو «رحمه/رحمة» خلافًا.
"""
import csv, json, re, sys
from pathlib import Path
from xml.sax.saxutils import escape

from collatex import Collation, collate

ROOT = Path(__file__).resolve().parent.parent
TRANS = ROOT / "transcriptions"
OUT = ROOT / "collation" / "out"

TASHKEEL = re.compile("[\\u0610-\\u061A\\u064B-\\u065F\\u0670\\u06D6-\\u06ED\\u0640]")
PAGE_MARK = re.compile(r"\[(?:ق|ص)?\s*[\d٠-٩]+\s*[أبظو]?\]")  # [ق12أ] علامات اللوحات


def normalize(word: str) -> str:
    w = TASHKEEL.sub("", word)
    w = re.sub("[إأآٱ]", "ا", w)
    w = w.replace("ى", "ي").replace("ة", "ه").replace("ؤ", "و").replace("ئ", "ي")
    return re.sub(r"[^\w]", "", w)


def load_witness(siglum: str) -> str:
    files = sorted((TRANS / siglum).glob("*.txt"))
    if not files:
        sys.exit(f"لا توجد ملفات نسخ في transcriptions/{siglum}/")
    text = "\n".join(f.read_text(encoding="utf-8") for f in files)
    text = PAGE_MARK.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def tokens(text: str):
    return [{"t": w, "n": normalize(w) or w} for w in text.split(" ") if w]


def main(sigla):
    OUT.mkdir(parents=True, exist_ok=True)
    data = {"witnesses": [{"id": s, "tokens": tokens(load_witness(s))} for s in sigla]}
    result = json.loads(collate(data, output="json", segmentation=False, near_match=True))

    table = result["table"]  # [witness][column] -> list of tokens | None
    cols = len(table[0])

    def reading(cell):
        return " ".join(tok["t"] for tok in cell) if cell else ""

    rows, apps = [], []
    for c in range(cols):
        cells = [reading(table[w][c]) for w in range(len(sigla))]
        norms = {" ".join(normalize(x) for x in r.split()) for r in cells}
        if len(norms) > 1:
            rows.append([c + 1, *cells])
            rdgs = "".join(
                f'<rdg wit="#{s}">{escape(r)}</rdg>' if r else f'<rdg wit="#{s}"/>'
                for s, r in zip(sigla, cells)
            )
            apps.append(f'  <app n="{c + 1}">{rdgs}</app>')

    (OUT / "table.txt").write_text(
        str(collate({"witnesses": data["witnesses"]}, output="table", segmentation=False, near_match=True)),
        encoding="utf-8",
    )
    with open(OUT / "variants.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["الموضع", *[f"نسخة {s}" for s in sigla]])
        w.writerows(rows)
    (OUT / "apparatus.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<listApp xmlns="http://www.tei-c.org/ns/1.0">\n' + "\n".join(apps) + "\n</listApp>\n",
        encoding="utf-8",
    )
    print(f"تمت المقابلة: {cols} عمودًا، منها {len(rows)} موضع خلاف. المخرجات في {OUT}")


if __name__ == "__main__":
    main(sys.argv[1:] or ["T", "M"])
