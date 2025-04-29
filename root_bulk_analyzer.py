#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Batch‑analyse Quranic triliteral roots with GPT‑4o (extended, token‑safe).

Updates – 2025‑04‑23
--------------------
* **NEW:** Output CSV keeps existing columns and only appends analytical + token‑usage columns.
* **Fix:** Section parser anchors headings; captures all 8 sections.
* **Retry:** Detects GPT refusals and reprompts up to `MAX_RETRIES`, logging each attempt.
* **Token metering:** Adds per‑root `tokens_prompt` + `tokens_completion` columns.
* **BUGFIX (2025‑04‑23 b):** Handle `resp.usage` as a Pydantic object (OpenAI ≥1.0)
  instead of a plain dict.
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

from dotenv import load_dotenv
from openai import OpenAI  # pip install --upgrade openai>=1.0
from quran_root_extractor import extract_verses_by_root

# ---------------------------------------------------------------------------
# Optional precise token counting – only for budget control
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
# Configuration
# ---------------------------------------------------------------------------
MODEL_NAME = "gpt-4o"
RATE_SLEEP = 1.0          # seconds between GPT calls
TOKEN_BUDGET = 25_000     # whole-prompt safety net (leave as is)
VERSES_TOKEN_LIMIT = 20_000   # <-- NEW: verses-only quota
MAX_VERSES = 100        # <-- NEW: verses-count ceiling
MAX_RETRIES = 1           # extra attempts after refusal

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

# (For brevity the middle of the template is unchanged; see previous version.)

# ---------------------------------------------------------------------------
# Section parser
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
# Helpers
# ---------------------------------------------------------------------------
client = OpenAI()
logs_dir = Path("logs"); logs_dir.mkdir(exist_ok=True)


def _compose_prompt(root: str, verses_block: str) -> str:
    return PROMPT_TEMPLATE.format(root=root, verses=verses_block)


def _build_prompt(
    root: str,
    verses: List[Dict[str, str | int]],
) -> Tuple[str, List[Dict]]:
    """
    Assemble the prompt, never exceeding MAX_VERSES verses and never letting the
    final prompt cross TOKEN_BUDGET.
    """
    selected: List[Dict] = []
    lines: List[str] = []

    for v in verses:
        if len(selected) >= MAX_VERSES:          # ← verses hard cap
            break

        line = f"({v['sura']}:{v['ayah']}) {v['text']}"
        candidate_prompt = _compose_prompt(root, "\n".join(lines + [line]))

        # keep the old token safety net
        if _count_tokens(candidate_prompt) > TOKEN_BUDGET:
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
    usage = resp.usage  # CompletionUsage (Pydantic model) or None
    p_tok = getattr(usage, "prompt_tokens", 0) if usage else 0
    c_tok = getattr(usage, "completion_tokens", 0) if usage else 0
    return content, p_tok, c_tok


def _gpt_ask(root: str, verses: List[Dict[str, str | int]]) -> Tuple[str, int, int]:
    prompt, _ = _build_prompt(root, verses)
    for attempt in range(MAX_RETRIES + 1):
        if attempt:
            print(
                f"[WARN] Reprompting {root} – previous reply looked like refusal "
                f"(attempt {attempt + 1}/{MAX_RETRIES + 1})"
            )
        else:
            print(f"[INFO] GPT-4o call → {root}")
        content, p_tok, c_tok = _gpt_request(prompt)
        (logs_dir / f"{root}_try{attempt + 1}.txt").write_text(content, encoding="utf-8")
        if not _looks_like_refusal(content):
            return content, p_tok, c_tok
        time.sleep(RATE_SLEEP)
    return content, p_tok, c_tok  # last attempt, even if refusal


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
    ap = argparse.ArgumentParser(description="Analyse triliteral roots with GPT-4o (token-safe).")
    ap.add_argument("--roots_csv", default="data/root_sample_1.csv")
    ap.add_argument("--out_csv",   default="data/output/roots_analysis.csv")
    ap.add_argument("--ayahs_dir", default="data/output/ayahs_json")
    ap.add_argument("--morph",     default="data/quran-morphology.txt")
    ap.add_argument("--xml",       default="data/quran-uthmani.xml")
    args = ap.parse_args()

    rows, orig_cols = _read_input_rows(Path(args.roots_csv))
    if not rows:
        sys.exit("[ERROR] ملف الإدخال لا يحتوي على جذور صالحة.")

    out_p   = Path(args.out_csv)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    ayah_dir = Path(args.ayahs_dir)
    ayah_dir.mkdir(parents=True, exist_ok=True)

    # -----------------------------------------------------------------------
    # 2️⃣  **RESUME SUPPORT** — skip roots already present in a partial CSV
    # -----------------------------------------------------------------------
    processed: set[str] = set()
    if out_p.is_file():
        with out_p.open(encoding="utf-8-sig") as fh:
            processed = {row.get("root") or row.get("الجذر")              # type: ignore
                         for row in csv.DictReader(fh) if (row.get("root") or row.get("الجذر"))}

    final_cols = orig_cols + [c for c in ANALYSIS_COLUMNS + TOKEN_COLUMNS if c not in orig_cols]

    # -----------------------------------------------------------------------
    # main loop
    # -----------------------------------------------------------------------
    for r in rows:
        root_val = (r.get("الجذر") or r.get("root") or "").strip()
        if not root_val:
            continue
        if root_val in processed:
            print(f"[SKIP] {root_val} already analysed.")
            continue

        # ---- original GPT + parsing logic (unchanged) ---------------------
        verses = extract_verses_by_root(root_val, args.morph, args.xml)
        (ayah_dir / f"{root_val}.json").write_text(
            json.dumps(verses, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        reply, p_tok, c_tok = _gpt_ask(root_val, verses)
        r.update(_parse_sections(reply))
        r["tokens_prompt"]     = p_tok
        r["tokens_completion"] = c_tok

        # ------------------------------------------------------------------
        # 3️⃣  **WRITE PROGRESS IMMEDIATELY** — append a row after each root
        # ------------------------------------------------------------------
        with out_p.open("a", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=final_cols)
            if fh.tell() == 0:          # file was just created
                w.writeheader()
            w.writerow(r)

        processed.add(root_val)         # so we can skip it if the app restarts
        time.sleep(RATE_SLEEP)

    print(f"[OK] CSV → {out_p}\n[OK] Ayah JSON → {ayah_dir}")

if __name__ == "__main__" and sys.argv[0].endswith("root_bulk_analyzer.py"):
    main()