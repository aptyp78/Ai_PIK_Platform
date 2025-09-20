#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, Any


def page_id(n: int) -> str:
    return f"p{int(n):03d}"


def build_coverage(unified_root: Path, pages_root: Path) -> Dict[str, Any]:
    cov: Dict[str, Any] = {}
    # Map titles to slugs
    def slugify(s: str) -> str:
        import unicodedata
        s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
        s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
        return s or "doc"

    for d in sorted([p for p in pages_root.iterdir() if p.is_dir()], key=lambda p: p.name.lower()):
        title = d.name
        slug = slugify(title)
        pfiles = sorted(d.glob("page-*.png"), key=lambda p: int(re.search(r"(\d+)", p.stem).group(1)))
        pages_total = len(pfiles)
        pages_done = 0
        regions_total = 0
        u_slug = unified_root / slug
        if u_slug.exists():
            for pf in pfiles:
                m = re.search(r"(\d+)", pf.stem)
                pid = page_id(int(m.group(1))) if m else None
                if not pid:
                    continue
                agg = u_slug / pid / "regions.json"
                if agg.exists():
                    pages_done += 1
                    try:
                        js = json.loads(agg.read_text(encoding="utf-8"))
                        regs = js.get("regions") or []
                        regions_total += int(js.get("count") or len(regs))
                    except Exception:
                        pass
        cov[slug] = {
            "pages_total": pages_total,
            "pages_done": pages_done,
            "frames_total": 0,
            "frames_done": 0,
            "regions_total": regions_total,
        }
    return cov


def main():
    ap = argparse.ArgumentParser(description="Refresh coverage.json from unified regions layout")
    ap.add_argument("--unified", default="out/visual/regions/gdino_sam2")
    ap.add_argument("--pages-root", default="out/page_images")
    ap.add_argument("--out", default="out/portal/coverage.json")
    args = ap.parse_args()

    unified = Path(args.unified)
    pages_root = Path(args.pages_root)
    cov = build_coverage(unified, pages_root)
    outp = Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(cov, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {outp} for {len(cov)} docs")


if __name__ == "__main__":
    main()

