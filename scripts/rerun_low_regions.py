#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple


def slugify(s: str) -> str:
    import unicodedata, re
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s or "doc"


def title_by_slug(pages_root: Path) -> Dict[str, str]:
    mp: Dict[str, str] = {}
    if not pages_root.exists():
        return mp
    for d in pages_root.iterdir():
        if d.is_dir():
            mp[slugify(d.name)] = d.name
    return mp


def count_regions(unified_root: Path, slug: str, pid: str) -> int:
    p = unified_root / slug / pid / "regions.json"
    if not p.exists():
        return 0
    try:
        js = json.loads(p.read_text(encoding="utf-8"))
        regs = js.get("regions") or []
        return int(js.get("count") or len(regs))
    except Exception:
        return 0


def page_image_for(pages_root: Path, title: str, pid: str) -> Path | None:
    # pid is pNNN
    try:
        n = int(pid[1:])
    except Exception:
        return None
    p = pages_root / title / f"page-{n}.png"
    return p if p.exists() else None


def run(cmd: List[str]) -> None:
    print("$", " ".join(cmd))
    subprocess.run(cmd, check=True)

def page_id_from_image(img: Path) -> str | None:
    import re
    m = re.search(r"page[-_]?(\d+)", img.name, flags=re.IGNORECASE)
    if not m:
        return None
    n = int(m.group(1))
    return f"p{n:03d}"

def aggregate_raw_to_unified(img: Path, unified_root: Path, grounded_root: Path, slug: str, pid: str) -> int:
    """Aggregate raw region-*.json from grounded_root/<stem>/regions into
    unified_root/<slug>/<pid>/regions.json. Returns count aggregated.
    """
    import json
    raw_dir = grounded_root / img.stem / "regions"
    if not raw_dir.exists():
        return 0
    regs = []
    rid = 1
    for j in sorted(raw_dir.glob("region-*.json")):
        try:
            r = json.loads(j.read_text(encoding="utf-8"))
        except Exception:
            continue
        # bbox: accept dict {x,y,w,h} or xywh list
        bb = r.get("bbox")
        if isinstance(bb, dict):
            x = int(bb.get("x", 0)); y = int(bb.get("y", 0)); w = int(bb.get("w", 0)); h = int(bb.get("h", 0))
            bbox = {"x": x, "y": y, "w": w, "h": h}
        elif isinstance(bb, list) and len(bb) == 4:
            bbox = {"x": int(bb[0]), "y": int(bb[1]), "w": int(bb[2]), "h": int(bb[3])}
        else:
            # maybe xyxy
            bb2 = r.get("gdino", {}).get("bbox_xyxy") if isinstance(r.get("gdino"), dict) else None
            if isinstance(bb2, list) and len(bb2) == 4:
                x0,y0,x1,y1 = [int(v) for v in bb2]
                bbox = {"x": x0, "y": y0, "w": max(1, x1-x0), "h": max(1, y1-y0)}
            else:
                continue
        gd = r.get("gdino") or {}
        cap = gd.get("phrase") or r.get("caption") or ""
        rec = {
            "rid": rid,
            "bbox": bbox,
            "text": r.get("text") or "",
            "caption": cap,
            "gdino": {k:v for k,v in gd.items() if k in {"conf","phrase"}},
        }
        regs.append(rec)
        rid += 1
    if not regs:
        return 0
    dst = unified_root / slug / pid
    dst.mkdir(parents=True, exist_ok=True)
    outj = {"count": len(regs), "regions": regs}
    (dst / "regions.json").write_text(json.dumps(outj, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(regs)


def main():
    ap = argparse.ArgumentParser(description="Re-run detection (tiled) for pages with too few regions (<threshold)")
    ap.add_argument("--unified-root", default="out/visual/regions/gdino_sam2")
    ap.add_argument("--pages-root", default="out/page_images")
    ap.add_argument("--outdir", default="out/visual/grounded_regions")
    ap.add_argument("--threshold", type=int, default=50)
    ap.add_argument("--limit", type=int, default=0, help="Max pages to re-detect (0 = no limit)")
    ap.add_argument("--grounding-model", default=os.getenv("GROUNDING_MODEL", ""))
    ap.add_argument("--sam-model", default=os.getenv("SAM_MODEL", ""))
    args = ap.parse_args()

    unified = Path(args.unified_root)
    pages_root = Path(args.pages_root)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    titles = title_by_slug(pages_root)
    to_redetect: List[Path] = []
    for slug_dir in sorted([p for p in unified.iterdir() if p.is_dir()], key=lambda p: p.name):
        slug = slug_dir.name
        for item in sorted([p for p in slug_dir.iterdir() if p.is_dir()]):
            pid = item.name
            if not pid.startswith("p"):
                continue
            c = count_regions(unified, slug, pid)
            if c >= args.threshold:
                continue
            title = titles.get(slug)
            if not title:
                continue
            img = page_image_for(pages_root, title, pid)
            if img:
                to_redetect.append(img)
            if args.limit and len(to_redetect) >= args.limit:
                break
        if args.limit and len(to_redetect) >= args.limit:
            break

    if not to_redetect:
        print("No pages below threshold; nothing to do.")
        return

    print(f"Pages to redetect (<{args.threshold} regions): {len(to_redetect)}")
    # Chunk images to avoid long CLI lines
    CHUNK = 16
    grounded_root = Path(args.outdir)
    unified_root = Path("out/visual/regions/gdino_sam2")
    for i in range(0, len(to_redetect), CHUNK):
        chunk = to_redetect[i:i+CHUNK]
        cmd = [
            "python3", "scripts/gdino_sam2_tiled.py",
            "--images", *[str(p) for p in chunk],
            "--outdir", str(outdir),
        ]
        if args.grounding_model:
            cmd += ["--grounding-model", args.grounding_model]
        if args.sam_model:
            cmd += ["--sam-model", args.sam_model]
        run(cmd)
        # Fallback aggregation to unified per image
        for img in chunk:
            pid = page_id_from_image(img)
            if not pid:
                continue
            # map image to slug using title_by_slug
            # find title by checking parent dir name under pages_root
            title = img.parent.name
            slug = slugify(title)
            try:
                agg_n = aggregate_raw_to_unified(img, unified_root, grounded_root, slug, pid)
                if agg_n:
                    print(f"[agg] {slug}/{pid}: {agg_n} regions → unified")
            except Exception as e:
                print(f"[agg] failed for {img}: {e}")

    # Overlays → metrics (migrate step covered by fallback aggregator above)
    try:
        run(["python3", "scripts/generate_overlays.py"])
    except Exception:
        pass
    try:
        run(["python3", "scripts/generate_metrics.py", "--out", "out/portal/metrics.json"])
        run(["python3", "scripts/generate_monitoring.py", "--metrics", "out/portal/metrics.json", "--coverage", "out/portal/coverage.json", "--trends", "out/portal/metrics_trends.json", "--out", "out/portal/monitoring/index.html"])
        run(["python3", "scripts/generate_readiness.py", "--metrics", "out/portal/metrics.json", "--out", "out/portal/readiness/index.html"])
    except Exception:
        pass


if __name__ == "__main__":
    main()
