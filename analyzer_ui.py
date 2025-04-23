#!/usr/bin/env python3
"""
Streamlit UI for **root_bulk_analyzer.py**  – live logs, accurate progress bar, persistent downloads.

• Upload CSV/Excel with a `root` column.
• Runs `root_bulk_analyzer.py` as an unbuffered subprocess so `[INFO] …` lines
  stream instantly.
• Displays:
    – A scrolling log (last 30 lines)
    – A progress bar that advances per root
    – A status line (Processed N/total)
• Caches the resulting CSV and ZIP bytes in `st.session_state` so download
  buttons remain after each click.

Run:
    streamlit run analyzer_ui.py
"""
from __future__ import annotations

import os, sys, uuid, shutil, tempfile, subprocess, re
from pathlib import Path

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------#
# Page setup
# ---------------------------------------------------------------------------#
st.set_page_config(page_title="Quran Root Bulk Analyzer", page_icon="📖", layout="centered")
st.title("📖 Quran Root Bulk Analyzer (GPT-4o)")

if "OPENAI_API_KEY" not in os.environ:
    st.warning("OPENAI_API_KEY is not set; the backend call may fail.")

# Persistent storage for downloads across reruns
for key in ("csv_data", "csv_name", "zip_data", "zip_name"):
    st.session_state.setdefault(key, None)

st.markdown("Upload a **CSV** or **Excel** file containing a column named **`root`**.")

# ---------------------------------------------------------------------------#
# File upload section
# ---------------------------------------------------------------------------#
file = st.file_uploader("Choose file", type=["csv", "xlsx", "xls"])

if file:
    # ---------- read table ----------
    try:
        df = pd.read_excel(file) if file.name.lower().endswith((".xlsx", ".xls")) else pd.read_csv(file)
    except Exception as e:
        st.error(f"Failed to read file: {e}")
        st.stop()

    if "root" not in df.columns:
        st.error("Column `root` not found in the uploaded file.")
        st.stop()

    total_roots = len(df)
    st.success(f"Loaded {total_roots:,} roots.")
    st.dataframe(df.head())

    out_csv_name = st.text_input("Output CSV filename", value="roots_analysis.csv")

    # ------------------------------------------------------------------- run
    if st.button("Run bulk analysis 🚀"):
        # reset previous downloads
        st.session_state.csv_data = None
        st.session_state.zip_data = None

        # placeholders drawn *before* spinner so they remain visible
        st.markdown("### Live progress")
        log_box     = st.empty()
        status_line = st.empty()
        pbar        = st.progress(0.0)

        with st.spinner("Running GPT-4o analysis – please wait …"):
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = Path(tmpdir)
                roots_csv = tmp_path / f"roots_{uuid.uuid4().hex}.csv"
                df.to_csv(roots_csv, index=False, encoding="utf-8-sig")

                ayah_dir = tmp_path / "ayahs_json"
                out_csv  = tmp_path / out_csv_name

                script_path = Path(__file__).with_name("root_bulk_analyzer.py")
                cmd = [sys.executable, "-u", str(script_path),
                       "--roots_csv", str(roots_csv),
                       "--out_csv",  str(out_csv),
                       "--ayahs_dir", str(ayah_dir)]

                logs: list[str] = []
                processed = 0
                info_rx = re.compile(r"^\[INFO].*call(?:\s+for\s+root)?\s*(?:→)?\s*(.+?)\s*(?:…|$)")

                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
                with proc:
                    for raw_line in proc.stdout:  # type: ignore
                        line = raw_line.rstrip()
                        logs.append(line)
                        log_box.code("\n".join(logs[-30:]), language="")

                        m = info_rx.match(line)
                        if m:
                            processed += 1
                            status_line.markdown(f"**Processed {processed}/{total_roots}:** {m.group(1)}")
                            pbar.progress(processed / total_roots)

                proc.wait()
                pbar.progress(1.0)
                status_line.markdown("**Analysis finished**")

                # -------- load outputs into session_state --------
                if out_csv.is_file():
                    st.session_state.csv_data = out_csv.read_bytes()
                    st.session_state.csv_name = out_csv_name
                if ayah_dir.is_dir() and any(ayah_dir.iterdir()):
                    zip_path = tmp_path / "ayahs_json.zip"
                    shutil.make_archive(zip_path.with_suffix(""), "zip", ayah_dir)
                    st.session_state.zip_data = zip_path.read_bytes()
                    st.session_state.zip_name = "ayahs_json.zip"

                st.success("Results ready – download below.")

# ---------------------------------------------------------------------------#
# Persistent download buttons
# ---------------------------------------------------------------------------#
if st.session_state.csv_data:
    st.download_button(
        "📥 Download analysis CSV",
        data=st.session_state.csv_data,
        file_name=st.session_state.csv_name,
        mime="text/csv",
        key="csv_dl",
    )

if st.session_state.zip_data:
    st.download_button(
        "📥 Download ayah JSONs (ZIP)",
        data=st.session_state.zip_data,
        file_name=st.session_state.zip_name,
        mime="application/zip",
        key="zip_dl",
    )