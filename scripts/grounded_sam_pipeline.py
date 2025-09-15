#!/usr/bin/env python3
"""
Grounded-SAM(2) pipeline skeleton for region proposal + segmentation.

This script outlines integration points without downloading weights by default.
Fill in model paths and enable the calls when ready.
"""
import argparse
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description="Grounded-SAM(2) pipeline skeleton")
    ap.add_argument("--images", nargs="+", help="Input page images (PNG)")
    ap.add_argument("--outdir", default="out/visual/grounded_sam", help="Output directory")
    ap.add_argument("--grounding-model", default="", help="Path/name for GroundingDINO weights")
    ap.add_argument("--sam-model", default="", help="Path/name for SAM/SAM2 weights")
    ap.add_argument("--prompts", nargs="*", default=["diagram", "table", "canvas", "legend", "node", "arrow"], help="Text prompts for GroundingDINO")
    args = ap.parse_args()

    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)

    # Pseudocode (enable when models are available):
    # 1) Load GroundingDINO (text-conditioned detector)
    # 2) For each image, run detection with prompt list -> boxes + scores
    # 3) For each box, run SAM/SAM2 to segment mask; save crops, masks, bboxes, scores
    # 4) Export JSON with regions including {bbox, mask_path, score, prompt}

    for img in args.images:
        print(f"[SKIP] Would process {img} with GroundingDINO+SAM; configure weights to enable.")

    print(f"Skeleton ready. To enable, install groundingdino + segment-anything and set model paths.")


if __name__ == "__main__":
    main()

