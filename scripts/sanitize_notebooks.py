#!/usr/bin/env python3
"""
Sanitize Jupyter notebooks for GitHub preview:
- Remove top-level metadata.widgets (causes "Invalid Notebook: 'state' key missing")
- Optionally normalize trivial fields

Usage:
  python scripts/sanitize_notebooks.py [paths...]

If no paths provided, scans notebooks/**/*.ipynb
"""
import json
import sys
from pathlib import Path


def sanitize_one(path: Path) -> bool:
    try:
        nb = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    changed = False
    md = nb.get("metadata")
    if isinstance(md, dict) and "widgets" in md:
        # GitHub nbconvert expects metadata.widgets.state; easier is to drop widgets block
        md.pop("widgets", None)
        nb["metadata"] = md
        changed = True
    # Ensure every cell.metadata is a dict
    for c in nb.get("cells", []) or []:
        if not isinstance(c.get("metadata"), dict):
            c["metadata"] = {}
            changed = True
    if changed:
        path.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
    return changed


def main(argv):
    args = argv[1:]
    if not args:
        args = [str(p) for p in Path("notebooks").rglob("*.ipynb")]
    touched = 0
    for ap in args:
        p = Path(ap)
        if p.is_file() and p.suffix == ".ipynb":
            if sanitize_one(p):
                print("sanitized:", p)
                touched += 1
    print("changed", touched, "notebooks")


if __name__ == "__main__":
    main(sys.argv)

