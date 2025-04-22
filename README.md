# Quran Root Analysis Toolkit

This repository provides three complementary Python scripts for extracting, listing and semantically analysing **triliteral Arabic roots** in the Qur’an.

| Script | Role |
| ------ | ---- |
| `extract_roots.py` | Scan the morphology file and output a **frequency‑sorted CSV** of every root that appears in the Qur'an. |
| `quran_root_extractor.py` | Given a single root (Arabic _or_ Buckwalter), return **all verses** in which that root occurs. |
| `root_bulk_analyzer.py` | Use **OpenAI GPT‑4o** to generate a rich semantic analysis (definition, synonyms, antonyms, etc.) for **many roots at once**. |

> **Last updated:** 2025-04-22

---

## 1. Quick start (recommended defaults)

```bash
# create a virtual environment (optional but recommended)
python -m venv .venv && source .venv/bin/activate

# install required packages
pip install -r requirements.txt  # see the section below if you don't have this file

# 1️⃣ extract a list of roots and counts
python extract_roots.py data/quran-morphology.txt

# 2️⃣ inspect all verses that contain the root rHm (رحم):
python quran_root_extractor.py rHm --out verses_rHm.json

# 3️⃣ run the bulk semantic analysis over a list of roots
python root_bulk_analyzer.py --roots_csv data/root_sample_1.csv
```

---

## 2. Prerequisites

* **Python ≥ 3.9**
* `pip install` the following PyPI packages (if you do not keep a `requirements.txt`):

  ```bash
  pip install openai python-dotenv
  ```

* **Data files** (place in the `data/` folder or point to them with CLI flags):

  | File | Source | Purpose |
  | --- | --- | --- |
  | `quran-morphology.txt` | Mustafa0x/quran-morphology ✦ TSV | Word‑level morphology with Buckwalter roots |
  | `quran-uthmani.xml` | Tanzil.net ✦ XML | Uthmani script Qur’an, used to fetch full verse text |

---

## 3. Environment variables

`root_bulk_analyzer.py` requires an **OpenAI API key**:

```bash
export OPENAI_API_KEY="sk‑..."
```

You may alternatively create a `.env` file in the project root:

```
OPENAI_API_KEY=sk‑...
```

> The script pauses for **1 second** between completions (`RATE_SLEEP`) to stay within the standard GPT‑4o rate limits. Adjust if you have a higher quota.

---

## 4. Script reference

### 4.1 `extract_roots.py`

| Position | Argument | Description |
| -------- | -------- | ----------- |
| 1 (required) | `MORPH_PATH` | Path to `quran-morphology.txt`. |
| 2 (optional) | `DEST_CSV` | Output file. Defaults to `roots_counts.csv` next to the source file. |

The output CSV has the columns: **root,count,forms** where *forms* is a `;`‑separated list of the surface forms encountered with their counts.

Example:

```bash
python extract_roots.py data/quran-morphology.txt data/roots_counts.csv
```

---

### 4.2 `quran_root_extractor.py`

```text
usage: quran_root_extractor.py ROOT [--morph PATH] [--xml PATH] [--out FILE]
```

`ROOT` can be Arabic (`رحم`) or Buckwalter (`rHm`).  
If you omit `--out`, the JSON is streamed to **stdout**.

Sample call:

```bash
python quran_root_extractor.py رحم \
       --morph data/quran-morphology.txt \
       --xml   data/quran-uthmani.xml \
       --out   verses_rHm.json
```

The JSON structure:

```jsonc
[
  {
    "surah": 1,
    "ayah": 3,
    "text": "ٱلرَّحْمَٰنِ ٱلرَّحِيمِ",
    "tokens": ["الرَّحْمَٰنِ", "الرَّحِيمِ"]
  },
  ...
]
```

---

### 4.3 `root_bulk_analyzer.py`

```text
usage: root_bulk_analyzer.py [--roots_csv ROOTS] [--out_csv OUT] [--morph PATH] [--xml PATH]
```

| Flag | Default | Meaning |
| ---- | ------- | ------- |
| `--roots_csv` | `data/root_sample_1.csv` | UTF‑8 CSV listing roots (column **الجذر** or **root**). |
| `--out_csv`   | `data/output/roots_analysis.csv` | Destination for the aggregated analysis. |
| `--morph`     | `data/quran-morphology.txt` | Morphology file for verse extraction. |
| `--xml`       | `data/quran-uthmani.xml` | Quran XML with Uthmani script. |

**Outputs**

* A CSV with the following Arabic headers  
  (`الجذر، الشرح، المرادفات، الأضداد، الفرق الدلالي، التحليل الدلالي للسياق، الملخص الدلالي`).
* Raw GPT replies per root in `logs/<root>.txt` for auditing.

> **Tip:** Tweak the `PROMPT_TEMPLATE` constant inside the script if you need a different explainer style.

---

## 5. Typical workflow

1. **Update/verify data**: make sure `quran-morphology.txt` and `quran-uthmani.xml` are fresh.
2. **Generate a ranked list** of roots with `extract_roots.py` and choose the ones you care about.
3. **Create a roots CSV** (or use the sample) and run `root_bulk_analyzer.py`.
4. **Review the logs** folder for any parsing anomalies; fix the prompt or parser as needed.
5. **Import the final CSV** into your linguistic tool or spreadsheet.

---

## 6. Repository layout

```text
.
├── data/
│   ├── quran-morphology.txt
│   ├── quran-uthmani.xml
│   └── root_sample_1.csv
├── logs/
├── extract_roots.py
├── quran_root_extractor.py
├── root_bulk_analyzer.py
└── README.md   ← you are here
```

---

## 7. Troubleshooting

* **`FileNotFoundError`**: Check the paths you pass to `--morph` or `--xml`.
* **`openai.error.RateLimitError`**: Increase `RATE_SLEEP` or upgrade your OpenAI quota.
* **Empty analysis rows**: The root might not exist in the morphology file; verify spelling.

---

## 8. Acknowledgements

* Morphology TSV adapted from **University of Leeds Quranic Arabic Corpus**.
* XML from **Tanzil.net** Uthmani script.
* Semantic analysis powered by **OpenAI GPT‑4o**.

---

Happy analysing!  
