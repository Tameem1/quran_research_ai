#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Batch-analyse Quranic triliteral roots with GPT-4o (token-safe).

Excel edition – 29 Apr 2025
───────────────────────────
▸ Writes progress to an internal **.tmp.csv** (resume-safe).
▸ When finished, converts that CSV to a real **.xlsx** workbook and moves it
  to the exact path given with --out_csv (or the default).
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd                   # ← NEW
from dotenv import load_dotenv
from openai import OpenAI
from quran_root_extractor import extract_verses_by_root

# ---------------------------------------------------------------------------
# Optional precise token counting
# ---------------------------------------------------------------------------
try:
    import tiktoken  # type: ignore

    _ENC = tiktoken.get_encoding("cl100k_base")

    def _count_tokens(text: str) -> int:
        return len(_ENC.encode(text))

except ModuleNotFoundError:  # pragma: no cover

    _ENC = None

    def _count_tokens(text: str) -> int:  # noqa: D401
        return max(len(text) // 3, len(text.split()))

# ---------------------------------------------------------------------------
# OpenAI + analysis configuration (unchanged)
# ---------------------------------------------------------------------------
MODEL_NAME = "gpt-4o"
RATE_SLEEP = 1.0
TOKEN_BUDGET = 25_000
VERSES_TOKEN_LIMIT = 20_000
MAX_VERSES = 100
MAX_RETRIES = 1

REFUSAL_PATTERNS = re.compile(
    r"آسف|عذرًا|لا\s+أ(?:ستطيع|قدر)|أ(?:عتذر|سف)|معذرة",
    re.I | re.M,
)

# ---------------------------------------------------------------------------
# Prompt template (Arabic)
# ---------------------------------------------------------------------------
PROMPT_TEMPLATE = """
الرجاء الالتزام الصارم بكل قسم مذكور أدناه دون تغيير الترتيب أو العناوين.  
 يُرجَى قِرَاءَةُ التَّعْلِيمَاتِ بِتَأَنٍّ ثُمَّ الإِجَابَةُ حَسْبَ النَّمَطِ الْمُحَدَّدِ فَقَط   

مَطْلُوبٌ مِنْكَ ما يَلِي، مُسْتَنِدًا حَصْرًا إِلَى مَعَاجِمٍ مَوْثُوقَةٍ (لِسَان العَرَب، القَامُوس المـحيط، مَوْقِع «مَعَانِي»)، وَبِلُغَةٍ عَرَبِيَّةٍ فُصْحَى سَلِسَةٍ تُنَاسِبُ فَهْمَ طِفْلٍ فِي الـ12 مِنْ عُمُرِهِ:  

1. **مفردات لسان العرب**  
   - أَعْطِنِي مَعْنَى الجَذْر في «لسان العرب» فَقَط.  
   - اشْرَح المَصْدَرَ الاسْميَّ وَالفِعْلِيَّ للجَذْر.  
   - خُذ عَيِّنَةً مِـن نُصوصِ «لسان العرب» (جُمْلَةً أو جُمْلَتَيْن لا أَكْثَر) ثُمَّ لَخِّصْهَا.  
   - اذْكُر أَشْهَرَ التَّصْرِيفَاتِ المُعَاصِرَةِ لِلْكَلِمَةِ (ثلاثة إلى خمسة).  
   - قَدِّم مِثَالًا بَسِيطًا مُوَضِّحًا لِلْمَعْنَى (لَا تَسْتَخْدِمْ آيَاتٍ قُرْآنِيَّةٍ هُنَا).  

2. **شرح لسان العرب**  
   - شَرْحٌ دَقِيقٌ لِلْكَلِمَةِ بِالاعْتِمَادِ عَلَى «لسان العرب» حَصْرًا، دُونَ مَصَادِرَ أُخْرَى.  

3. **الشرح (سياق قرآني)**  
   - فَسِّر مَعْنَى الجَذْر كَمَا يَرِدُ فِي الآيَاتِ المُرْفَقَةِ.  
   - بَيِّن المَعْنَى الأَسَاسِيَّ وَالمَعَانِي الثَّانَوِيَّةَ.  

4. **المرادفات** – أَقْرَبُ الكَلِمَاتِ مَعْنًى لِلْجَذْر (3–5 كلمات).  

5. **الأضداد** – كَلِمَاتٌ تُعْطِي المَعْنَى المُضَادَّ (3–5 كلمات).  

6. **الفرق الدلالي**  
   - قَارِن بَيْنَ الجَذْر وَاثْنَينِ مِنْ مَرَادِفَاتِهِ.  
   - وَضِّح خُصُوصِيَّةَ اسْتِعْمَالِهِ فِي القُرْآنِ.  

7. **التحليل الدلالي للسياق**  
   - حَلِّل طُرُقَ تَوْظِيفِ الجَذْرِ فِي الآيَاتِ المُخْتَلِفَةِ.  
   - أَشِرْ إِلَى الغَرَضِ البَلَاغِيِّ وَالأَثَرِ الدِّلالِيِّ لِكُلِّ اسْتِعْمَالٍ.  

8. **الملخص الدلالي**  
   - فِقْرَةٌ مُوَجَزَةٌ تَجْمَعُ بَيْنَ المَعْنَى المَعْجَمِيِّ، القُرْآنِيِّ، وَالسِّيَاقِيِّ.  

**التنسيق المطلوب للإجابة (حافظْ عَلَى العَناوِينِ حَرْفِيًّا وَبِتَرْتِيبِهَا):**  
مفردات لسان العرب: ()  
شرح لسان العرب: ()  
الشرح: ()  
المرادفات: ()  
الأضداد: ()  
الفرق الدلالي: ()  
التحليل الدلالي للسياق: ()  
الملخص الدلالي: ()  

**مُدْخَلَاتُ القَالِب** (لا تَعْدِلْ عَلَيْهَا، بَلْ اسْتَخْدِمْهَا كَمَا هِيَ):  
الجذر: {root}  
الآيات:  
{verses}  

**قُيُودٌ:**  
- لا تُضِفْ أَقْسَامًا أَوْ عَنَاوِينَ غَيْرَ مَذْكُورَةٍ.  
- لا تَسْتَشْهِدْ بِآيَاتٍ خَارِجَ الآيات المذكورة.  
- لا تُدْرِجْ مَصَادِرَ جَدِيدَةً غَيْرَ «لسان العرب» فِي الفِقْرَتَيْن 1 و 2.  
- لُغَتُكَ يَجِبُ أَنْ تَكُونَ فَصِيحَةً وَسَلِسَةً، تَلِيقُ بِقَارِئٍ فِي سِنِّ 12 عَامًا.  
- تَجَنَّبِ الإِطَالَةَ؛ كُلُّ فِقْرَةٍ مَا بَيْنَ 2–6 جُمَلٍ إِلَّا إِذَا طُلِبَ غَيْرُ ذٰلِكَ صَرَاحَةً.  

**اِلْتَزِمِ الدِّقَّةَ وَالإِيجَازَ فِي آنٍ مَعًا، وَاتَّبِعْ التَّرْتِيبَ نَفْسَهُ بِدُونِ تَبْدِيلٍ.**
"""

# ---------------------------------------------------------------------------
# Section regex & column lists
# ---------------------------------------------------------------------------
SECTION_RE = re.compile(
    r"^\s*مفردات لسان العرب:\s*(.*?)\s*"
    r"^\s*شرح لسان العرب:\s*(.*?)\s*"
    r"^\s*الشرح:\s*(.*?)\s*"
    r"^\s*المرادفات:\s*(.*?)\s*"
    r"^\s*الأضداد:\s*(.*?)\s*"
    r"^\s*الفرق الدلالي:\s*(.*?)\s*"
    r"^\s*التحليل الدلالي للسياق:\s*(.*?)\s*"
    r"^\s*الملخص الدلالي:\s*(.*)$",
    re.S | re.M,
)

ANALYSIS_COLUMNS = [
    "مفردات لسان العرب",
    "شرح لسان العرب",
    "الشرح",
    "المرادفات",
    "الأضداد",
    "الفرق الدلالي",
    "التحليل الدلالي للسياق",
    "الملخص الدلالي",
]
TOKEN_COLUMNS = ["tokens_prompt", "tokens_completion"]

# ---------------------------------------------------------------------------
# Excel helper
# ---------------------------------------------------------------------------
def _csv_to_xlsx(csv_path: Path, xlsx_dest: Path) -> None:
    """Convert *csv_path* to Excel workbook *xlsx_dest* (overwrite if exists)."""
    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    df.to_excel(xlsx_dest, index=False, engine="openpyxl")

# ---------------------------------------------------------------------------
# GPT helpers (unchanged from original file)
# ---------------------------------------------------------------------------
client = OpenAI()
logs_dir = Path("logs"); logs_dir.mkdir(exist_ok=True)

def _compose_prompt(root: str, verses_block: str) -> str:
    return PROMPT_TEMPLATE.format(root=root, verses=verses_block)

def _build_prompt(root: str, verses: List[Dict[str, str | int]]) -> Tuple[str, List[Dict]]:
    selected: List[Dict] = []
    lines: List[str] = []
    for v in verses:
        if len(selected) >= MAX_VERSES:
            break
        line = f"({v['sura']}:{v['ayah']}) {v['text']}"
        prospect = _compose_prompt(root, "\n".join(lines + [line]))
        if _count_tokens(prospect) > TOKEN_BUDGET:
            break
        lines.append(line)
        selected.append(v)
    return _compose_prompt(root, "\n".join(lines)), selected

def _looks_like_refusal(text: str) -> bool:
    if not text.strip():
        return True
    if len(text.strip()) < 50 and REFUSAL_PATTERNS.search(text):
        return True
    if REFUSAL_PATTERNS.search(text) and text.count("\n") <= 2:
        return True
    return False

def _gpt_request(prompt: str) -> Tuple[str, int, int]:
    resp = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=1024,
    )
    content = resp.choices[0].message.content.strip()
    usage = resp.usage
    return content, getattr(usage, "prompt_tokens", 0), getattr(usage, "completion_tokens", 0)

def _gpt_ask(root: str, verses: List[Dict[str, str | int]]) -> Tuple[str, int, int]:
    prompt, _ = _build_prompt(root, verses)
    for attempt in range(MAX_RETRIES + 1):
        if attempt:
            print(f"[WARN] Reprompting {root} (attempt {attempt + 1}/{MAX_RETRIES + 1})")
        else:
            print(f"[INFO] GPT-4o call → {root}")
        content, p_tok, c_tok = _gpt_request(prompt)
        (logs_dir / f"{root}_try{attempt + 1}.txt").write_text(content, encoding="utf-8")
        if not _looks_like_refusal(content):
            return content, p_tok, c_tok
        time.sleep(RATE_SLEEP)
    return content, p_tok, c_tok  # last attempt

def _parse_sections(text: str) -> Dict[str, str]:
    m = SECTION_RE.search(text)
    if not m:
        d = {k: "" for k in ANALYSIS_COLUMNS}
        d["الشرح"] = text.strip()
        return d
    return {ANALYSIS_COLUMNS[i]: m.group(i + 1).strip() for i in range(8)}

def _read_input_rows(csv_path: Path) -> Tuple[List[Dict[str, str]], List[str]]:
    with csv_path.open(encoding="utf-8-sig") as fh:
        rdr = csv.DictReader(fh)
        rows = list(rdr)
        return rows, (rdr.fieldnames or [])

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser(description="Analyse triliteral roots with GPT-4o and export Excel.")
    ap.add_argument("--roots_csv", default="data/root_sample_1.csv")
    ap.add_argument("--out_csv",   default="data/output/roots_analysis.xlsx",
                    help="Destination Excel file (will be overwritten).")
    ap.add_argument("--ayahs_dir", default="data/output/ayahs_json")
    ap.add_argument("--morph",     default="data/quran-morphology.txt")
    ap.add_argument("--xml",       default="data/quran-uthmani.xml")
    args = ap.parse_args()

    # Internally use a .tmp.csv for checkpointing
    tmp_csv_path = Path(args.out_csv).with_suffix(".tmp.csv")
    rows, orig_cols = _read_input_rows(Path(args.roots_csv))
    if not rows:
        sys.exit("[ERROR] ملف الإدخال لا يحتوي على جذور صالحة.")

    tmp_csv_path.parent.mkdir(parents=True, exist_ok=True)
    ayah_dir = Path(args.ayahs_dir); ayah_dir.mkdir(parents=True, exist_ok=True)

    # Resume support
    processed: set[str] = set()
    if tmp_csv_path.is_file():
        with tmp_csv_path.open(encoding="utf-8-sig") as fh:
            processed = {row.get("root") or row.get("الجذر")
                         for row in csv.DictReader(fh)
                         if (row.get("root") or row.get("الجذر"))}

    final_cols = orig_cols + [c for c in ANALYSIS_COLUMNS + TOKEN_COLUMNS if c not in orig_cols]

    for r in rows:
        root_val = (r.get("الجذر") or r.get("root") or "").strip()
        if not root_val or root_val in processed:
            continue

        verses = extract_verses_by_root(root_val, args.morph, args.xml)
        (ayah_dir / f"{root_val}.json").write_text(
            json.dumps(verses, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        reply, p_tok, c_tok = _gpt_ask(root_val, verses)
        r.update(_parse_sections(reply))
        r["tokens_prompt"]     = p_tok
        r["tokens_completion"] = c_tok

        with tmp_csv_path.open("a", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=final_cols)
            if fh.tell() == 0:
                w.writeheader()
            w.writerow(r)

        processed.add(root_val)
        time.sleep(RATE_SLEEP)

    # -----------------------------------------------------------------------
    # Finalise Excel workbook exactly at args.out_csv
    # -----------------------------------------------------------------------
    final_xlsx = Path(args.out_csv).with_suffix(".xlsx")
    _csv_to_xlsx(tmp_csv_path, final_xlsx)

    print(
        f"[OK] XLSX  → {final_xlsx}\n"
        f"[OK] Temp  → {tmp_csv_path}\n"
        f"[OK] Ayah JSON → {ayah_dir}"
    )

if __name__ == "__main__" and sys.argv[0].endswith("root_bulk_analyzer.py"):
    main()