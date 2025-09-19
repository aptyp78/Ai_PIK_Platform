#!/usr/bin/env python3
"""
Batch-detect visual regions on all rendered PNG pages using GroundedDINO + SAM2.

Scans --pages-root (default: out/page_images) for *.png and runs
scripts/grounded_sam_detect.py in chunks.
"""
import argparse
import math
import os
import subprocess
from pathlib import Path
from typing import Iterable, List


def chunked(seq: List[Path], size: int) -> Iterable[List[Path]]:
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


def main() -> None:
    ap = argparse.ArgumentParser(description="Batch run GroundedDINO+SAM2 on all pages")
    ap.add_argument("--pages-root", default="out/page_images", help="Root with rendered page images")
    ap.add_argument("--outdir", default="out/visual/grounded_regions", help="Output directory for detections")
    ap.add_argument(
        "--prompts",
        nargs="+",
        default=["diagram", "canvas", "table", "legend", "node", "arrow", "textbox"],
        help="Detection prompts",
    )
    ap.add_argument("--grounding-model", default=os.getenv("GROUNDING_MODEL", ""))
    ap.add_argument("--sam-model", default=os.getenv("SAM_MODEL", ""))
    ap.add_argument("--batch-size", type=int, default=64, help="Images per invocation (avoid too long argv)")
    ap.add_argument("--limit", type=int, default=0, help="Limit images processed (0 = all)")
    args = ap.parse_args()

    root = Path(args.pages_root)
    if not root.exists():
        raise SystemExit(f"Pages root not found: {root}")

    images = sorted(root.rglob("*.png"))
    if args.limit:
        images = images[: args.limit]
    if not images:
        print("No images found under:", root)
        return

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    prompts = args.prompts
    chunk_size = max(1, args.batch_size)

    for group in chunked(images, chunk_size):
        cmd = [
            "python",
            "scripts/grounded_sam_detect.py",
            "--images",
            *[str(p) for p in group],
            "--outdir",
            str(outdir),
            "--prompts",
            *prompts,
        ]
        if args.grounding_model:
            cmd += ["--grounding-model", args.grounding_model]
        if args.sam_model:
            cmd += ["--sam-model", args.sam_model]
        print("Running:", " ".join(cmd[:10]), "... (+more)")
        subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
