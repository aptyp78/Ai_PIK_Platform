#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import math


def load_elements(src: Path, pages: List[int]) -> Dict[int, List[Dict[str, Any]]]:
    data = json.loads(src.read_text())
    by_page: Dict[int, List[Dict[str, Any]]] = {}
    for el in data:
        md = el.get("metadata", {}) or {}
        page = md.get("page_number")
        if page is None:
            continue
        page = int(page)
        if pages and page not in pages:
            continue
        # decode bbox from coordinates/bbox
        bbox = None
        coords = md.get("coordinates") or el.get("coordinates")
        if isinstance(coords, dict) and isinstance(coords.get("points"), list):
            pts = coords["points"]
            xs = [p[0] for p in pts if isinstance(p, (list, tuple)) and len(p) >= 2]
            ys = [p[1] for p in pts if isinstance(p, (list, tuple)) and len(p) >= 2]
            if xs and ys:
                x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
                bbox = {"x": float(x0), "y": float(y0), "w": float(x1 - x0), "h": float(y1 - y0)}
        if bbox is None:
            bb = md.get("bbox") or el.get("bbox")
            if isinstance(bb, dict) and all(k in bb for k in ("x", "y", "width", "height")):
                bbox = {"x": float(bb["x"]), "y": float(bb["y"]), "w": float(bb["width"]), "h": float(bb["height"])}
        t = (el.get("type") or "").strip()
        txt = (el.get("text") or "").strip()
        img_b64 = el.get("image_base64") or md.get("image_base64")
        by_page.setdefault(page, []).append({
            "type": t,
            "text": txt,
            "bbox": bbox,
            "image_b64": img_b64 if isinstance(img_b64, str) else None,
        })
    return by_page


def bbox_union(a: Dict[str, float], b: Dict[str, float]) -> Dict[str, float]:
    x0 = min(a["x"], b["x"])
    y0 = min(a["y"], b["y"])
    x1 = max(a["x"] + a["w"], b["x"] + b["w"])
    y1 = max(a["y"] + a["h"], b["y"] + b["h"])
    return {"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0}


def bbox_iou(a: Dict[str, float], b: Dict[str, float]) -> float:
    ax0, ay0, ax1, ay1 = a["x"], a["y"], a["x"] + a["w"], a["y"] + a["h"]
    bx0, by0, bx1, by1 = b["x"], b["y"], b["x"] + b["w"], b["y"] + b["h"]
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    iw, ih = max(0.0, ix1 - ix0), max(0.0, iy1 - iy0)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    aarea = (ax1 - ax0) * (ay1 - ay0)
    barea = (bx1 - bx0) * (by1 - by0)
    return inter / (aarea + barea - inter + 1e-6)


def bbox_dist(a: Dict[str, float], b: Dict[str, float]) -> float:
    axc = a["x"] + a["w"] / 2.0
    ayc = a["y"] + a["h"] / 2.0
    bxc = b["x"] + b["w"] / 2.0
    byc = b["y"] + b["h"] / 2.0
    return math.hypot(axc - bxc, ayc - byc)


def cluster_elements(elems: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # Greedy clustering by IoU or proximity
    items = [e for e in elems if e.get("bbox")]
    used = [False] * len(items)
    clusters: List[Dict[str, Any]] = []
    # Sort top-to-bottom
    order = sorted(range(len(items)), key=lambda i: (items[i]["bbox"]["y"], items[i]["bbox"]["x"]))
    for idx in order:
        if used[idx]:
            continue
        base = items[idx]
        box = dict(base["bbox"])  # type: ignore
        texts = [base.get("text", "")] if base.get("text") else []
        imgs = [base.get("image_b64")] if base.get("image_b64") else []
        used[idx] = True
        changed = True
        while changed:
            changed = False
            for j in order:
                if used[j]:
                    continue
                bj = items[j]
                if not bj.get("bbox"):
                    continue
                iou = bbox_iou(box, bj["bbox"])  # type: ignore
                dist = bbox_dist(box, bj["bbox"])  # type: ignore
                # Merge if overlap or close (threshold tuned conservatively)
                if iou > 0.15 or dist < max(box["h"], bj["bbox"]["h"]) * 0.6:
                    box = bbox_union(box, bj["bbox"])  # type: ignore
                    if bj.get("text"):
                        texts.append(bj["text"])  # type: ignore
                    if bj.get("image_b64"):
                        imgs.append(bj["image_b64"])  # type: ignore
                    used[j] = True
                    changed = True
        clusters.append({
            "bbox": box,
            "text": "\n".join(texts).strip(),
            "image_b64": imgs[0] if imgs else None,
        })
    return clusters


def dump_regions(outdir: Path, page: int, regions: List[Dict[str, Any]]) -> None:
    rdir = outdir / f"{page}" / "regions"
    rdir.mkdir(parents=True, exist_ok=True)
    for i, r in enumerate(regions, start=1):
        with open(rdir / f"region-{i}.json", "w", encoding="utf-8") as f:
            json.dump(r, f, ensure_ascii=False, indent=2)


def main():
    ap = argparse.ArgumentParser(description="Detect regions by clustering element bboxes (pilot)")
    ap.add_argument("--json", required=True, help="Path to Unstructured JSON source")
    ap.add_argument("--pages", nargs="+", type=int, help="Pages to process")
    ap.add_argument("--outdir", default="out/visual/regions_detect", help="Output directory for detected regions")
    ap.add_argument("--pdf", default=None, help="Optional source PDF to fallback to full-page region if no bboxes")
    args = ap.parse_args()

    src = Path(args.json)
    pages = [int(p) for p in args.pages]
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    by_page = load_elements(src, pages)
    pdf_path = Path(args.pdf) if args.pdf else None
    for page, elems in sorted(by_page.items()):
        regs = cluster_elements(elems)
        if not regs and pdf_path and pdf_path.exists():
            # Fallback: use full-page rendered image if available
            # Expect render_pages.py to have produced out/page_images/<pdfstem>/page-<p>.png
            img_dir = Path("out/page_images") / pdf_path.stem
            png = img_dir / f"page-{page}.png"
            if png.exists():
                b64 = (png.read_bytes()).hex()  # placeholder to avoid huge base64 in memory
                # Use real base64
                import base64
                b64 = base64.b64encode(png.read_bytes()).decode("utf-8")
                regs = [{"bbox": None, "text": "", "image_b64": b64}]
        dump_regions(outdir, page, regs)
        print(f"Detected {len(regs)} regions on page {page} -> {outdir}/{page}/regions/")


if __name__ == "__main__":
    main()
