#!/usr/bin/env python3
# quran_root_extractor.py  –  19 Apr 2025
#
#  ▸ Extract every (sura, ayah, text) that contains a given triliteral root
#    from a Quran morphology TSV file.  Works with either:
#       • quranic‑corpus‑morphology‑0.4.txt  (old format)
#       • quran‑morphology.txt by mustafa0x   (new format)
#
#    Differences handled automatically:
#       • Location field may be wrapped in parentheses or bare.
#       • "ROOT:" tags may be Arabic letters (new) or Buckwalter (old).
#       • User may supply Arabic or Buckwalter on the command line.
#
# ---------------------------------------------------------------------------
from __future__ import annotations

import argparse, json, re, sys
from pathlib import Path
from typing import Iterable, Tuple, List, Dict

from lxml import etree   # pip install lxml>=5.2

# ---------------------------------------------------------------------------
# Helpers – Buckwalter transliteration ⇄ Arabic
# ---------------------------------------------------------------------------

# Minimal one‑to‑one Buckwalter → Arabic map (covers 28 consonants + hamza).
_BUCK2AR_MAP: dict[str, str] = {
    "'": "ء",  # hamza
    'A': 'ا', 'b': 'ب', 't': 'ت', 'v': 'ث', 'j': 'ج', 'H': 'ح', 'x': 'خ',
    'd': 'د', '*': 'ذ', 'r': 'ر', 'z': 'ز', 's': 'س', '$': 'ش', 'S': 'ص',
    'D': 'ض', 'T': 'ط', 'Z': 'ظ', 'E': 'ع', 'g': 'غ', 'f': 'ف', 'q': 'ق',
    'k': 'ك', 'l': 'ل', 'm': 'م', 'n': 'ن', 'h': 'ه', 'w': 'و', 'y': 'ي',
    'p': 'ة'  # ta‑marbuta (rare in roots)
}
_BUCK2AR = str.maketrans(_BUCK2AR_MAP)
_AR2BUCK = {v: k for k, v in _BUCK2AR_MAP.items()}


def buck2arabic(bw: str) -> str:
    """Translate a Buckwalter triliteral to Arabic letters."""
    return bw.translate(_BUCK2AR)


def arabic2buck(ar: str) -> str:
    """Translate Arabic root to Buckwalter (best‑effort)."""
    return ''.join(_AR2BUCK.get(ch, ch) for ch in ar)

# ---------------------------------------------------------------------------
# Regexes for the two corpus flavours
# ---------------------------------------------------------------------------

# Location:  either "(2:4:1:1)\t…"   or   "2:4:1:1\t…"
_LOC_PATT = re.compile(r"^\(?([0-9]+):([0-9]+):")

# Field 4 contains pipe‑separated tags, one of which is ROOT:…
# We do not pre‑compile because we just split on '|'.

# ---------------------------------------------------------------------------

def _iter_matches(root_query: str, morph_path: Path) -> Iterable[Tuple[int, int]]:
    """Yield (sura, ayah) pairs that contain *root_query* (Arabic or Buckwalter)."""

    # Determine both Arabic and Buckwalter representations for reliable match
    if root_query.isascii():                 # Buckwalter given
        root_bw = root_query.lower()
        root_ar = buck2arabic(root_bw)
    else:                                    # Arabic given
        root_ar = root_query
        root_bw = arabic2buck(root_ar).lower()

    with morph_path.open(encoding="utf‑8") as fh:
        for line in fh:
            if not line or line[0] in "#\r\n":
                continue  # comments & blanks

            # Quick filter to drop lines unlikely to match (cheap substring)
            if (root_ar not in line) and (f"root:{root_bw}" not in line.lower()):
                continue

            # Extract sura & ayah
            m = _LOC_PATT.match(line)
            if not m:
                continue  # malformed location
            sura, ayah = map(int, m.groups())

            # Confirm by scanning tag field (index 3)
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 4:
                continue
            for tag in fields[3].split("|"):
                if not tag.lower().startswith("root:"):
                    continue
                tag_val = tag.split(":", 1)[1]
                if tag_val == root_ar or tag_val.lower() == root_bw:
                    yield sura, ayah
                    break

# ---------------------------------------------------------------------------

def extract_verses_by_root(
        root: str,
        morph_path: str | Path = "quran-morphology.txt",
        xml_path:   str | Path = "quran-uthmani.xml",
) -> List[Dict[str, str | int]]:
    """Return a list of {sura, ayah, text} dicts that contain *root*."""

    verses = sorted(set(_iter_matches(root, Path(morph_path))))
    tree   = etree.parse(str(xml_path))       # ElementTree
    hits   = tree.xpath                       # shorthand

    out: List[Dict[str, str | int]] = []
    for s, a in verses:
        aya_nodes = hits(f"/quran/sura[@index='{s}']/aya[@index='{a}']")
        if aya_nodes:
            out.append({"sura": s, "ayah": a,
                        "text": aya_nodes[0].get("text")})
    return out

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli() -> None:
    ap = argparse.ArgumentParser(description="Find every verse containing a triliteral root (Arabic or Buckwalter).")
    ap.add_argument("root", help="Root in Buckwalter (e.g. 'rHm') or Arabic (e.g. 'رحم')")
    ap.add_argument("--morph", default="data/quran-morphology.txt",
                    help="Path to morphology TSV")
    ap.add_argument("--xml",   default="data/quran-uthmani.xml",
                    help="Path to Uthmani Quran XML")
    ap.add_argument("--out",   help="Write results to JSON file")
    args = ap.parse_args()

    verses = extract_verses_by_root(args.root, args.morph, args.xml)
    if args.out:
        Path(args.out).write_text(json.dumps(verses, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
    else:
        json.dump(verses, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")

# ---------------------------------------------------------------------------

if __name__ == "__main__":
    _cli()

# Using the Quran Corpus https://corpus.quran.com/:
# python find_stem.py rHm --morph /Users/tameem/Documents/ai-quran-research-assistant/data/quranic-corpus-morphology-0.4.txt --out verses_rHm.json
# Using the mustafa0x/quran-morphology Github
# python find_stem.py رحم --morph data/quran-morphology.txt --out verses_rHm.json
