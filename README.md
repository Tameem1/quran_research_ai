# Quran Root Analysis Toolkit

This repository provides tools for extracting, listing, and semantically analysing **triliteral Arabic roots** in the Qur’an, now with a **Streamlit** web interface:

| Script / App               | Role |
| -------------------------- | ---- |
| `extract_roots.py`         | Scan the morphology file and output a **frequency-sorted CSV** of every root that appears in the Qur'an. |
| `quran_root_extractor.py`  | Given a single root (Arabic _or_ Buckwalter), return **all verses** in which that root occurs (as JSON or stdout). |
| `root_bulk_analyzer.py`    | Use **OpenAI GPT-4o** to generate a rich semantic analysis (definition, synonyms, antonyms, etc.) for **many roots at once**. |
| **Streamlit UI**           | A one-page web app (`analyzer_ui.py`) for uploading a CSV/Excel of roots and downloading the bulk analysis. |

> **Last updated:** 2025-04-23

---

## 1. Quick start (command-line)

```bash
# create a virtual environment (optional but recommended)
python -m venv .venv && source .venv/bin/activate

# install required packages
pip install -r requirements.txt

# 1️⃣ extract a list of roots and counts
python extract_roots.py data/quran-morphology.txt

# 2️⃣ inspect all verses that contain the root rHm (رحم):
python quran_root_extractor.py rHm --out verses_rHm.json

# 3️⃣ run the bulk semantic analysis over a list of roots:
python root_bulk_analyzer.py --roots_csv data/root_sample_1.csv
```

## 2. Prerequisites

- **Python ≥ 3.9**
- Install dependencies via:

  ```bash
  pip install -r requirements.txt
  ```

- **Data files** (place in `data/` or point with CLI flags):

  | File                  | Source                               | Purpose                                    |
  | --------------------- | ------------------------------------ | ------------------------------------------ |
  | `quran-morphology.txt`| Mustafa0x/quran-morphology (TSV)    | Word-level morphology with Buckwalter roots|
  | `quran-uthmani.xml`   | Tanzil.net (XML)                    | Uthmani script Qur’an for full verses      |

## 3. Environment variables

`root_bulk_analyzer.py` and the Streamlit app require an **OpenAI API key**:

```bash
export OPENAI_API_KEY="sk-..."
```

Alternatively, create a `.env` file in the project root with:

```
OPENAI_API_KEY=sk-...
```

## 4. Streamlit UI

We’ve provided **`analyzer_ui.py`** for a browser-based workflow:

1. **Upload** a CSV or Excel file with a column named **`root`** (triliteral roots).
2. Click **Run bulk analysis 🚀** to call `root_bulk_analyzer.py` under the hood.
3. **Download** the resulting CSV of semantic analyses.

Run it with:

```bash
streamlit run analyzer_ui.py
```

## 5. Script reference

### 5.1 `extract_roots.py`

| Position | Argument    | Description                                                   |
| -------- | ----------- | ------------------------------------------------------------- |
| 1 (req)  | `MORPH_PATH`| Path to `quran-morphology.txt`.                               |
| 2 (opt)  | `DEST_CSV`  | Output file. Defaults to `roots_counts.csv`.                 |

Outputs **CSV** with columns: `root,count,forms`.

### 5.2 `quran_root_extractor.py`

```text
usage: quran_root_extractor.py ROOT [--morph PATH] [--xml PATH] [--out FILE]
```

- **ROOT**: Arabic (e.g. `رحم`) or Buckwalter (e.g. `rHm`).
- Defaults: `--morph data/quran-morphology.txt`, `--xml data/quran-uthmani.xml`.
- If `--out` omitted, writes to stdout as JSON.

### 5.3 `root_bulk_analyzer.py`

```text
usage: root_bulk_analyzer.py [--roots_csv ROOTS] [--out_csv OUT] [--morph PATH] [--xml PATH]
```

| Flag             | Default                            | Meaning                                            |
| ---------------- | ---------------------------------- | -------------------------------------------------- |
| `--roots_csv`    | `data/root_sample_1.csv`           | CSV listing roots (column **root** or **الجذر**).  |
| `--out_csv`      | `data/output/roots_analysis.csv`   | Destination for the aggregated analysis CSV.       |
| `--morph`        | `data/quran-morphology.txt`        | Morphology file for verse extraction.             |
| `--xml`          | `data/quran-uthmani.xml`           | Quran XML with Uthmani script.                    |

**Outputs**: A UTF-8 CSV with Arabic headers:

```
الجذر، الشرح، المرادفات، الأضداد، الفرق الدلالي، التحليل الدلالي للسياق، الملخص الدلالي
```

Raw GPT replies per root are saved under `logs/<root>.txt`.

## 6. Typical workflow

1. Update/verify data: ensure `quran-morphology.txt` and `quran-uthmani.xml` are fresh.
2. Generate a ranked list of roots with `extract_roots.py`.
3. Create or edit your roots CSV (column **root**) and run `root_bulk_analyzer.py` or use the Streamlit UI.
4. Review `logs/` for raw GPT outputs if needed.
5. Import the final CSV into your linguistic tool or spreadsheet.

## 7. Repository layout

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
├── analyzer_ui.py              ← Streamlit interface
├── requirements.txt            ← dependency list
└── README.md                   ← you are here
```

## 8. Troubleshooting

- **`FileNotFoundError`**: Check the paths you pass to `--morph`, `--xml`, or running the Streamlit app.
- **`openai.error.RateLimitError`**: Increase `RATE_SLEEP` in `root_bulk_analyzer.py` or upgrade your quota.
- **Missing `root` column**: The Streamlit UI expects a column named `root` (singular).
- **Empty analysis rows**: Verify spelling of roots or check `logs/` for GPT parsing issues.

## 9. Acknowledgements

- Morphology TSV adapted from **University of Leeds Quranic Arabic Corpus**.
- XML from **Tanzil.net** Uthmani script.
- Semantic analysis powered by **OpenAI GPT-4o**.

Happy analysing!
