#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Batch‑analyse Quranic triliteral roots with GPT‑4o.

▪ Reads a UTF‑8 CSV of roots (column name can be "الجذر" or "root").
▪ For each root it fetches all verses via `quran_root_extractor.extract_verses_by_root`.
▪ Sends the verses to GPT‑4o with the user‑supplied Arabic prompt template.
▪ Logs every raw GPT reply in ./logs/<root>.txt for inspection.
▪ Parses the labelled sections and writes a consolidated CSV with columns:
  الجذر، الشرح، المرادفات، الأضداد، الفرق الدلالي، التحليل الدلالي للسياق، الملخص الدلالي

Usage examples
--------------
  # simplest (all defaults)
  $ ./root_bulk_analyzer.py

  # specify morphology / XML / IO paths
  $ ./root_bulk_analyzer.py roots.csv out.csv \
        --morph data/quran-morphology.txt --xml data/quran-uthmani.xml
"""
from __future__ import annotations
import argparse, csv, re, sys, time
from pathlib import Path
from typing import Dict, List

from openai import OpenAI               # pip install --upgrade openai>=1.0
from quran_root_extractor import extract_verses_by_root
from dotenv import load_dotenv
load_dotenv()
# ---------- configuration ---------- #
MODEL_NAME = "gpt-4o"
RATE_SLEEP = 1.0       # seconds between calls (nicely)
PROMPT_TEMPLATE = (
    "* مستندًا إلى معاجم موثوقة مثل لسان العرب، القاموس المحيط، وموقع معاني. "
    "بلغة فصيحة وبأسلوب يناسب فهم شخص يبلغ من العمر 12 سنة. "
    "اريد منك ان تشرح معنى الجذر المرفق مستفيداً من الآيات المرفقة المذكور فيها هذا الجذر. "
    "مع ذكر المرادفات والأضداد وشرح الفرق الدلالي بين الكلمة ومرادفاتها بالإضافة الى التحليل الدلالي للسياق. "
    "اليك شرح مبسط عن كل من المتطلبات: “ ⁠الشرح:(شرح دقيق لمعنى الجذر كما ورد في السياق القرآني، مع توضيح المعنى الأساسي والمعاني الثانوية) "
    "المرادفات: (كلمات تحمل معاني قريبة من الجذر) الأضداد: (كلمات تحمل المعاني المضادة أو العكسية للجذر)"
    "الفرق الدلالي: (شرح الفرق بين الجذر وبعض مرادفاته، وتوضيح خصوصية استعماله في القرآن)"
    "التحليل الدلالي للسياق:(تحليل كيف وُظّف الجذر في سياقات مختلفة، وما الغرض البلاغي والدلالي من كل استعمال) "
    "الملخص الدلالي:(فقرة موجزة تلخص الدلالة العامة للجذر، تجمع المعنى المعجمي والقرآني والسياقي، وتبرز جوهر الاستخدام القرآني)”\n\n"
    "المرفق:\nالجذر: {root}\nالآيات:\n{verses}\n\n"
    "إجابتك يجب أن تكون على النموذج التالي:\n"
    "الشرح: ()\nالمرادفات: ()\nالأضداد: ()\nالفرق الدلالي: ()\nالتحليل الدلالي للسياق: ()\nالملخص الدلالي: ()"
)

SECTION_RE = re.compile(
    r"الشرح:\s*(.*?)\s*"
    r"المرادفات:\s*(.*?)\s*"
    r"الأضداد:\s*(.*?)\s*"
    r"الفرق الدلالي:\s*(.*?)\s*"
    r"التحليل الدلالي للسياق:\s*(.*?)\s*"
    r"الملخص الدلالي:\s*(.*)",
    re.S
)

COLUMNS = [
    "الجذر", "الشرح", "المرادفات", "الأضداد", "الفرق الدلالي",
    "التحليل الدلالي للسياق", "الملخص الدلالي"
]

# ---------- helpers ---------- #

client = OpenAI()
logs_dir = Path("logs"); logs_dir.mkdir(exist_ok=True)

def _gpt_ask(root: str, verses: List[Dict[str, str | int]]) -> str:
    verses_str = "\n".join(f"({v['sura']}:{v['ayah']}) {v['text']}" for v in verses)
    prompt = PROMPT_TEMPLATE.format(root=root, verses=verses_str)

    print(f"[INFO] ⟳  GPT‑4o call for root {root} …", flush=True)
    resp = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=1024,
    )
    content = resp.choices[0].message.content.strip()
    # log raw response
    (logs_dir / f"{root}.txt").write_text(content, encoding="utf-8")
    return content


def _parse_sections(text: str) -> Dict[str, str]:
    m = SECTION_RE.search(text)
    if not m:
        # graceful fallback – return whole text in الشرح, leave others blank
        return {
            "الشرح": text, "المرادفات": "", "الأضداد": "", "الفرق الدلالي": "",
            "التحليل الدلالي للسياق": "", "الملخص الدلالي": ""
        }
    labels = ["الشرح", "المرادفات", "الأضداد", "الفرق الدلالي",
              "التحليل الدلالي للسياق", "الملخص الدلالي"]
    return {label: m.group(i+1).strip() for i, label in enumerate(labels)}


def _read_roots(csv_path: Path) -> List[str]:
    with csv_path.open(encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if "الجذر" in row and row["الجذر"].strip():
                yield row["الجذر"].strip()
            elif "root" in row and row["root"].strip():
                yield row["root"].strip()

# ---------- main ---------- #

def main() -> None:
    ap = argparse.ArgumentParser(description="Analyse triliteral roots with GPT‑4o.")
    ap.add_argument("--roots_csv", nargs="?", default="data/root_sample_1.csv", help="CSV containing a column 'الجذر' or 'root'")
    ap.add_argument("--out_csv",   nargs="?", default="data/output/roots_analysis.csv", help="Output CSV file (UTF‑8)")
    ap.add_argument("--morph", default="data/quran-morphology.txt", help="Path to morphology TSV")
    ap.add_argument("--xml",   default="data/quran-uthmani.xml", help="Path to Uthmani Quran XML")
    args = ap.parse_args()

    roots = list(_read_roots(Path(args.roots_csv)))
    if not roots:
        sys.exit("[ERROR] لم يتم العثور على جذور في ملف الإدخال.")

    rows = []
    for r in roots:
        verses = extract_verses_by_root(r, args.morph, args.xml)
        if not verses:
            print(f"[WARN] لا توجد آيات للجذر {r}")
            rows.append({"الجذر": r, **{c: "" for c in COLUMNS[1:]}})
            continue

        reply = _gpt_ask(r, verses)
        parts = _parse_sections(reply)
        rows.append({"الجذر": r, **parts})
        time.sleep(RATE_SLEEP)

    # write CSV
    with Path(args.out_csv).open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"[OK] ✔  Written {len(rows)} rows → {args.out_csv}")

if __name__ == "__main__" and sys.argv[0].endswith("root_bulk_analyzer.py"):
    main()