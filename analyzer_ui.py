#!/usr/bin/env python3
"""
Streamlit front-end for root_bulk_analyzer.py  (2025-04-23)

• Upload CSV/Excel with a column `root`.
• Invokes root_bulk_analyzer.py, which now produces:
      1. CSV semantic analysis
      2. Directory of per-root ayah JSON files
• Offers download buttons for the CSV and a ZIP of the JSON files.

Run:
    streamlit run analyzer_ui.py
"""
from __future__ import annotations

import os
import sys
import uuid
import shutil
import tempfile
import zipfile
from pathlib import Path

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------#
# Page layout
# ---------------------------------------------------------------------------#
st.set_page_config(page_title="Quran Root Bulk Analyzer", page_icon="📖", layout="centered")
st.title("📖 Quran Root Bulk Analyzer (GPT-4o)")

if "OPENAI_API_KEY" not in os.environ:
    st.warning("OPENAI_API_KEY is not set in the environment.")

st.markdown("Upload a **CSV** or **Excel** file containing a column named **`root`**.")


# ---------------------------------------------------------------------------#
# File upload
# ---------------------------------------------------------------------------#
uploaded = st.file_uploader("Choose a file", type=["csv", "xlsx", "xls"])

if uploaded is not None:
    # read dataframe
    try:
        df = (
            pd.read_excel(uploaded)
            if uploaded.name.lower().endswith((".xlsx", ".xls"))
            else pd.read_csv(uploaded)
        )
    except Exception as e:
        st.error(f"Failed to read file: {e}")
        st.stop()

    if "root" not in df.columns:
        st.error("Column `root` not found.")
        st.stop()

    st.success(f"Loaded {len(df):,} rows.")
    st.dataframe(df.head())

    out_csv_name = st.text_input("Output CSV filename", "roots_analysis.csv")

    if st.button("Run bulk analysis 🚀"):
        with st.spinner("Running GPT-4o analysis… this may take a while"):
            with tempfile.TemporaryDirectory() as tmp:
                tmp = Path(tmp)
                roots_csv = tmp / f"roots_{uuid.uuid4().hex}.csv"
                df.to_csv(roots_csv, index=False, encoding="utf-8-sig")

                ayah_dir = tmp / "ayahs_json"
                out_csv  = tmp / out_csv_name

                # call backend
                import root_bulk_analyzer

                backup_argv = sys.argv.copy()
                try:
                    sys.argv = [
                        "root_bulk_analyzer.py",
                        "--roots_csv", str(roots_csv),
                        "--out_csv",  str(out_csv),
                        "--ayahs_dir", str(ayah_dir),
                    ]
                    root_bulk_analyzer.main()
                finally:
                    sys.argv = backup_argv

                # download buttons
                if out_csv.is_file():
                    st.download_button(
                        "📥 Download analysis CSV",
                        data=out_csv.read_bytes(),
                        file_name=out_csv_name,
                        mime="text/csv",
                    )
                else:
                    st.error("CSV was not generated.")

                if ayah_dir.is_dir() and any(ayah_dir.iterdir()):
                    zip_path = tmp / "ayahs_json.zip"
                    shutil.make_archive(zip_path.with_suffix(""), "zip", ayah_dir)
                    st.download_button(
                        "📥 Download ayah JSONs (ZIP)",
                        data=zip_path.read_bytes(),
                        file_name="ayahs_json.zip",
                        mime="application/zip",
                    )
                else:
                    st.warning("No ayah JSON files produced.")

            st.success("Done! 🎉")