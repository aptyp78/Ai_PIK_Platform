#!/usr/bin/env python3
import argparse
import base64
from pathlib import Path
from typing import List, Tuple

import cv2  # type: ignore
import numpy as np  # type: ignore


def load_image(path: Path):
    img = cv2.imread(str(path))
    if img is None:
        raise SystemExit(f"Failed to read image: {path}")
    return img


def find_regions(img) -> List[Tuple[int, int, int, int]]:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    thr = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                cv2.THRESH_BINARY_INV, 35, 11)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
    dil = cv2.dilate(thr, kernel, iterations=1)
    cnts, _ = cv2.findContours(dil, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    regions = []
    H, W = gray.shape
    min_area = (W * H) * 0.01
    for c in cnts:
        x, y, w, h = cv2.boundingRect(c)
        if w * h < min_area:
            continue
        ar = w / float(h + 1e-6)
        if ar > 20 or ar < 0.05:
            continue
        regions.append((x, y, w, h))
    regions.sort(key=lambda r: (r[1], r[0]))
    return regions


def write_regions(outroot: Path, name: str, img, regions: List[Tuple[int, int, int, int]]):
    rdir = outroot / name / "regions"
    rdir.mkdir(parents=True, exist_ok=True)
    for i, (x, y, w, h) in enumerate(regions, start=1):
        crop = img[y:y+h, x:x+w]
        ok, buf = cv2.imencode('.png', crop)
        if not ok:
            continue
        b64 = base64.b64encode(buf.tobytes()).decode('utf-8')
        (rdir / f"region-{i}.json").write_text(
            '{"bbox": {"x": %d, "y": %d, "w": %d, "h": %d}, "text": "", "image_b64": "%s"}' % (x, y, w, h, b64),
            encoding='utf-8'
        )


def main():
    ap = argparse.ArgumentParser(description="CV segmentation for arbitrary images into regions")
    ap.add_argument("--images", nargs="+", help="Image paths (PNG/JPG)")
    ap.add_argument("--outdir", default="out/visual/cv_frames", help="Output directory root")
    args = ap.parse_args()

    outroot = Path(args.outdir)
    outroot.mkdir(parents=True, exist_ok=True)

    for imgp in args.images:
        p = Path(imgp)
        name = p.stem
        img = load_image(p)
        regs = find_regions(img)
        if not regs:
            H, W = img.shape[:2]
            regs = [(0, 0, W, H)]
        write_regions(outroot, name, img, regs)
        print(f"CV segmented {p.name} -> {len(regs)} regions at {outroot/name}")


if __name__ == "__main__":
    main()

