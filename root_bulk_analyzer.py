#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Batch‑analyse Quranic triliteral roots with GPT‑4o (extended, token‑safe).

Updates – 2025‑04‑23
--------------------
* **Precise token guard** – uses *tiktoken* when available to count tokens and
  trims *only the verse list* so that the **entire prompt ≤ 22 000 tokens**.
  (Buffer leaves ~8 k tokens for the model’s reply and stays below the org‑wide
  30 k TPM limit.)
* **Ayah JSON export** unchanged (`--ayahs_dir`).
* CSV header fixed (`writer.writeheader()`).
"""
from __future__ import annotations

import argparse, csv, json, re, sys, time
from pathlib import Path
from typing import Dict, List

from dotenv import load_dotenv
from openai import OpenAI                     # pip install --upgrade openai>=1.0
from quran_root_extractor import extract_verses_by_root

# optional precise token counting
try:
    import tiktoken  # type: ignore
    _ENC = tiktoken.get_encoding("cl100k_base")
    def _count_tokens(text: str) -> int:
        return len(_ENC.encode(text))
except ModuleNotFoundError:                   # fall back to rough estimate
    _ENC = None
    def _count_tokens(text: str) -> int:
        # ≈1 token / 3 chars or 1 token / word – use larger
        return max(len(text) // 3, len(text.split()))

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MODEL_NAME        = "gpt-4o"
RATE_SLEEP        = 1.0            # seconds between GPT calls
TOKEN_BUDGET      = 29_000         # prompt must stay under this

PROMPT_TEMPLATE = (
    "* مستندًا إلى معاجم موثوقة مثل لسان العرب، القاموس المحيط، وموقع معاني. "
    "بلغة فصيحة وبأسلوب يناسب فهم شخص يبلغ من العمر 12 سنة. "
    "اريد منك ان تشرح معنى الجذر المرفق مستفيداً من الآيات المرفقة المذكور فيها هذا الجذر. "
    "مع ذكر المرادفات والأضداد وشرح الفرق الدلالي بين الكلمة ومرادفاتها بالإضافة الى التحليل الدلالي للسياق. "
    "اليك شرح مبسط عن كل من المتطلبات: \n"
    "شرح لسان العرب: (شرح دقيق لمعنى الكلمة معتمداً على لسان العرب حصراً لا تحضر أي معلومات من الخارج)\n"
    "⁠الشرح:(شرح دقيق لمعنى الجذر كما ورد في السياق القرآني، مع توضيح المعنى الأساسي والمعاني الثانوية)\n"
    "المرادفات: (كلمات تحمل معاني قريبة من الجذر)\n"
    "الأضداد: (كلمات تحمل المعاني المضادة أو العكسية للجذر)\n"
    "الفرق الدلالي: (شرح الفرق بين الجذر وبعض مرادفاته، وتوضيح خصوصية استعماله في القرآن)\n"
    "التحليل الدلالي للسياق:(تحليل كيف وُظّف الجذر في سياقات مختلفة، وما الغرض البلاغي والدلالي من كل استعمال) \n"
    "الملخص الدلالي:(فقرة موجزة تلخص الدلالة العامة للجذر، تجمع المعنى المعجمي والقرآني والسياقي، وتبرز جوهر الاستخدام القرآني)\n\n"
    "المرفق:\nالجذر: {root}\nالآيات:\n{verses}\n\n"
    "إجابتك يجب أن تكون على النموذج التالي:\n"
    "شرح لسان العرب: ()\nالشرح: ()\nالمرادفات: ()\nالأضداد: ()\nالفرق الدلالي: ()\nالتحليل الدلالي للسياق: ()\nالملخص الدلالي: ()"
)

SECTION_RE = re.compile(
    r"شرح لسان العرب:\s*(.*?)\s*"
    r"الشرح:\s*(.*?)\s*"
    r"المرادفات:\s*(.*?)\s*"
    r"الأضداد:\s*(.*?)\s*"
    r"الفرق الدلالي:\s*(.*?)\s*"
    r"التحليل الدلالي للسياق:\s*(.*?)\s*"
    r"الملخص الدلالي:\s*(.*)",
    re.S,
)

COLUMNS = [
    "الجذر", "شرح لسان العرب", "الشرح", "المرادفات", "الأضداد",
    "الفرق الدلالي", "التحليل الدلالي للسياق", "الملخص الدلالي",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
client   = OpenAI()
logs_dir = Path("logs"); logs_dir.mkdir(exist_ok=True)

def _compose_prompt(root: str, verses_block: str) -> str:
    """Fill template but *only* varying the verses block."""
    return PROMPT_TEMPLATE.format(root=root, verses=verses_block)


def _build_prompt(root: str, verses: List[Dict[str, str | int]]) -> tuple[str, List[Dict]]:
    """Return (prompt, verses_used) so that prompt ≤ TOKEN_BUDGET tokens."""
    selected: List[Dict] = []
    verses_lines: list[str] = []
    for v in verses:
        line = f"({v['sura']}:{v['ayah']}) {v['text']}"
        candidate_lines = verses_lines + [line]
        prompt = _compose_prompt(root, "\n".join(candidate_lines))
        if _count_tokens(prompt) > TOKEN_BUDGET:
            break
        verses_lines.append(line)
        selected.append(v)
    return _compose_prompt(root, "\n".join(verses_lines)), selected


def _gpt_ask(root: str, verses: List[Dict[str, str | int]]) -> str:
    prompt, _ = _build_prompt(root, verses)
    print(f"[INFO] GPT‑4o call → {root}")
    resp = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=1024,
    )
    content = resp.choices[0].message.content.strip()
    (logs_dir / f"{root}.txt").write_text(content, encoding="utf-8")
    return content


def _parse_sections(text: str) -> Dict[str, str]:
    m = SECTION_RE.search(text)
    if not m:
        return {k: (text if k == "الشرح" else "") for k in COLUMNS[1:]}
    return {COLUMNS[i+1]: m.group(i+1).strip() for i in range(7)}


def _read_roots(csv_path: Path):
    with csv_path.open(encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            root_val = row.get("الجذر") or row.get("root")
            if root_val and root_val.strip():
                yield root_val.strip()

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Analyse triliteral roots with GPT‑4o (token‑safe).")
    ap.add_argument("--roots_csv", default="data/root_sample_1.csv")
    ap.add_argument("--out_csv",   default="data/output/roots_analysis.csv")
    ap.add_argument("--ayahs_dir", default="data/output/ayahs_json")
    ap.add_argument("--morph", default="data/quran-morphology.txt")
    ap.add_argument("--xml",   default="data/quran-uthmani.xml")
    args = ap.parse_args()

    roots = list(_read_roots(Path(args.roots_csv)))
    if not roots:
        sys.exit("[ERROR] ملف الإدخال لا يحتوي على جذور صالحة.")

    ayah_dir = Path(args.ayahs_dir); ayah_dir.mkdir(parents=True, exist_ok=True)

    rows: List[Dict[str, str]] = []
    for root in roots:
        verses = extract_verses_by_root(root, args.morph, args.xml)
        # save verses regardless of GPT success
        (ayah_dir / f"{root}.json").write_text(json.dumps(verses, ensure_ascii=False, indent=2), encoding="utf-8")

        if not verses:
            print(f"[WARN] لا توجد آيات للجذر {root}")
            rows.append({"الجذر": root, **{c: "" for c in COLUMNS[1:]}})
            continue

        reply = _gpt_ask(root, verses)
        rows.append({"الجذر": root, **_parse_sections(reply)})
        time.sleep(RATE_SLEEP)

    out_csv = Path(args.out_csv); out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader(); writer.writerows(rows)

    print(f"[OK] CSV → {out_csv}\n[OK] Ayah JSON → {ayah_dir}")


if __name__ == "__main__" and sys.argv[0].endswith("root_bulk_analyzer.py"):
    main()
