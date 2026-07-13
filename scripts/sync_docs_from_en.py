# -*- coding: utf-8 -*-
"""Doc workflow helper — EN is source of truth for in-app Guide/README/Release Notes.

Usage:
  1. Edit GUIDE.en.md / README.en.md / RELEASE_NOTES.en.md
  2. Update GUIDE.md / README.md / RELEASE_NOTES.md (VN translation) to match
  3. Or run this script to print a checklist and verify both sides exist

This script does NOT machine-translate. It validates pairing and reminds
that VN files must not lag EN after rule changes.
"""
from __future__ import annotations

import os
import sys

if hasattr(sys.stdout, "reconfigure") and (sys.stdout.encoding or "").lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAIRS = [
    ("GUIDE.en.md", "GUIDE.md"),
    ("README.en.md", "README.md"),
    ("RELEASE_NOTES.en.md", "RELEASE_NOTES.md"),
]


def main() -> int:
    os.chdir(ROOT)
    print("Doc source of truth: *.en.md")
    print("VN translations: GUIDE.md, README.md, RELEASE_NOTES.md")
    print("-" * 50)
    ok = True
    for en, vn in PAIRS:
        en_path = os.path.join(ROOT, en)
        vn_path = os.path.join(ROOT, vn)
        en_ok = os.path.isfile(en_path)
        vn_ok = os.path.isfile(vn_path)
        en_sz = os.path.getsize(en_path) if en_ok else 0
        vn_sz = os.path.getsize(vn_path) if vn_ok else 0
        status = "OK" if en_ok and vn_ok and en_sz > 50 and vn_sz > 50 else "MISSING/THIN"
        if status != "OK":
            ok = False
        print(f"  [{status}] {en} ({en_sz} B)  →  {vn} ({vn_sz} B)")
        if en_ok:
            with open(en_path, "r", encoding="utf-8") as f:
                head = f.readline().strip()
            print(f"         EN head: {head[:80]}")
        if vn_ok:
            with open(vn_path, "r", encoding="utf-8") as f:
                head = f.readline().strip()
            print(f"         VN head: {head[:80]}")
    print("-" * 50)
    if not ok:
        print("Fix missing/thin files before release.")
        return 1
    print("Both languages present. After editing EN, update VN translation.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
