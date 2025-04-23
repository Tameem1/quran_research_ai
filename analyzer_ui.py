#!/usr/bin/env python3
"""
Streamlit UI for **root_bulk_analyzer.py**
-----------------------------------------
A simple web interface that lets a user:
1. Upload a **CSV** or **Excel** file containing a column named **"root"**.
2. Invoke the GPT‑4o‑powered semantic analysis implemented in `root_bulk_analyzer.py`.
3. Download the resulting analysis CSV.

Run with:
    streamlit run root_bulk_streamlit_app.py

Prerequisites:
    pip install streamlit pandas openai python-dotenv
    # and of course the modules of this repository must be importable

Environment:
    Make sure the **OPENAI_API_KEY** environment variable is set, or place it
    in a `.env` file alongside this script.
"""
from __future__ import annotations

import os
import sys
import uuid
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
load_dotenv()
# --- check OpenAI key up‑front ----------------------------------------------
if "OPENAI_API_KEY" not in os.environ:
    st.warning(
        "The environment variable OPENAI_API_KEY is not set. Please set it before running the analysis.")

# --- page config -------------------------------------------------------------
st.set_page_config(page_title="Quran Root Bulk Analyzer", page_icon="📖", layout="centered")

st.title("📖 Quran Root Bulk Analyzer (GPT‑4o)")

st.markdown(
    """
Upload a **CSV** or **Excel** file that contains a column named **`root`** with
triliteral roots you wish to analyse. The app will run **root_bulk_analyzer.py**
in the background and return a CSV to download.
    """
)

# --- file upload -------------------------------------------------------------
uploaded_file = st.file_uploader("Choose a CSV or Excel file", type=["csv", "xlsx", "xls"], accept_multiple_files=False)

if uploaded_file is not None:
    # ---------- read the uploaded table ---------- #
    try:
        if uploaded_file.name.lower().endswith((".xlsx", ".xls")):
            roots_df = pd.read_excel(uploaded_file)
        else:
            roots_df = pd.read_csv(uploaded_file)
    except Exception as exc:
        st.error(f"❌ Could not read the file: {exc}")
        st.stop()

    if "root" not in roots_df.columns:
        st.error("❌ The uploaded file does **not** contain a column named `root`.")
        st.stop()

    st.success(f"✔ Loaded {len(roots_df):,} rows.")
    st.dataframe(roots_df.head())

    # ---------- output file name ---------- #
    default_out_name = "roots_analysis.csv"
    out_name = st.text_input("Output CSV filename", value=default_out_name)

    # ---------- action button ---------- #
    if st.button("Run bulk analysis 🚀"):
        with st.spinner("Running GPT‑4o analysis – this may take a while…"):
            # save a temporary CSV as-is (already has column 'root')
            with tempfile.TemporaryDirectory() as tmpdir:
                tmpdir_path = Path(tmpdir)

                roots_csv_path = tmpdir_path / f"roots_{uuid.uuid4().hex}.csv"
                roots_df.to_csv(roots_csv_path, index=False, encoding="utf-8-sig")

                out_csv_path = tmpdir_path / out_name

                # ---------- call root_bulk_analyzer programmatically ---------- #
                import root_bulk_analyzer  # local module in repo

                # Preserve original sys.argv and restore after the call
                orig_argv = sys.argv.copy()
                try:
                    sys.argv = [
                        "root_bulk_analyzer.py",
                        "--roots_csv", str(roots_csv_path),
                        "--out_csv", str(out_csv_path),
                    ]
                    root_bulk_analyzer.main()
                finally:
                    sys.argv = orig_argv

                # ---------- provide download ---------- #
                if out_csv_path.is_file():
                    with out_csv_path.open("rb") as fh:
                        st.download_button(
                            label="📥 Download analysis CSV",
                            data=fh.read(),
                            file_name=out_name,
                            mime="text/csv",
                        )
                    st.success("Analysis completed successfully! 🎉")
                else:
                    st.error("⚠ The analysis did not produce an output file. Please check the server logs.")
