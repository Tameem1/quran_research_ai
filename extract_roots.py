#!/usr/bin/env python3
"""
Extract every root in QuranMorphology.txt and write
a CSV file <root, count>, sorted by frequency.
Usage:
    python extract_roots.py  data/quran-morphology.txt  [roots_counts.csv]
"""

from collections import Counter
import csv
import re
import sys
from pathlib import Path

ROOT_RX = re.compile(r"ROOT:([^|]+)")        # capture the Buckwalter root token


def extract_roots(src: Path) -> tuple[Counter, dict[str, set[str]]]:
    """
    Return (Counter, dict) where
        • Counter maps Buckwalter root ➜ frequency, and
        • dict maps root ➜ Counter (surface form ➜ occurrences).
    Only lines that have a 'ROOT:' tag are counted.
    """
    counter = Counter()
    forms: dict[str, Counter] = {}
    with src.open(encoding="utf-8") as fh:
        for line in fh:
            m_root = ROOT_RX.search(line)
            if not m_root:
                continue
            root = m_root.group(1)
            counter[root] += 1

            # add the surface form (column 2) to the set of forms for this root
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 2:
                surface = parts[1]
                root_forms = forms.setdefault(root, Counter())
                root_forms[surface] += 1
    return counter, forms


def write_csv(counter: Counter, forms: dict[str, set[str]], dest: Path) -> None:
    """
    Write <root,count,forms> rows to *dest*, sorted by descending count then α‑order.
    The *forms* column lists each surface form followed by its frequency in
    parentheses, e.g.  رَحْمٰن(3);رَحِيم(2).
    """
    with dest.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["root", "count", "forms"])
        for root, cnt in sorted(counter.items(), key=lambda t: (-t[1], t[0])):
            fc = forms.get(root, Counter())
            form_list = ";".join(
                f"{form}({cnt})"
                for form, cnt in sorted(fc.items(), key=lambda t: (-t[1], t[0]))
            )
            w.writerow([root, cnt, form_list])


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("Supply path to QuranMorphology.txt")

    src = Path(sys.argv[1]).expanduser().resolve()
    dest = Path(sys.argv[2]).expanduser().resolve() if len(sys.argv) > 2 else src.with_name("roots_counts.csv")

    counter, forms = extract_roots(src)
    write_csv(counter, forms, dest)
    print(f"Wrote {len(counter):,} distinct roots → {dest}")


if __name__ == "__main__":
    main()