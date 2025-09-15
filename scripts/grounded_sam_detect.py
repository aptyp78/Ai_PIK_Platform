#!/usr/bin/env python3
import argparse
import base64
import os
from pathlib import Path
from typing import List, Tuple


def require_packages():
    missing = []
    try:
        import groundingdino  # type: ignore
    except Exception:
        missing.append("groundingdino")
    # Try SAM v1 first
    has_sam = True
    try:
        import segment_anything  # type: ignore
    except Exception:
        has_sam = False
    # Try SAM2
    has_sam2 = True
    try:
        import sam2  # type: ignore
    except Exception:
        has_sam2 = False
    if (not has_sam) and (not has_sam2):
        missing.append("segment-anything or sam2")
    if missing:
        raise SystemExit(
            "Missing packages: "
            + ", ".join(missing)
            + "\nSee docs/GROUNDED_SAM_SETUP.md for install instructions."
        )


def detect_regions_with_grounded(images: List[Path], outdir: Path, grounding_model: str, sam_model: str, prompts: List[str]):
    # NOTE: This is a placeholder to keep the script light.
    # In a real setup, you would:
    #  1) Load GroundingDINO model and tokenizer
    #  2) For each image and prompt, run detection -> boxes + scores
    #  3) Load SAM/SAM2 and for each box run segmentation -> mask/crop
    #  4) Save out JSON per region (bbox + base64 crop) under <stem>/regions/
    # Here we only ensure directory structure and provide a helpful message.
    for img in images:
        stem = img.stem
        rdir = outdir / stem / "regions"
        rdir.mkdir(parents=True, exist_ok=True)
        # Fallback: create a single region that is the whole image, so downstream can run
        try:
            import PIL.Image as Image  # type: ignore
        except Exception:
            Image = None
        b64 = None
        if Image is not None:
            im = Image.open(img).convert("RGB")
            import io

            buf = io.BytesIO()
            im.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        with open(rdir / "region-1.json", "w", encoding="utf-8") as f:
            f.write(
                '{"bbox": {"x": 0, "y": 0, "w": -1, "h": -1}, "text": "", "image_b64": "%s"}'
                % (b64 or "")
            )
        print(f"[INFO] Placeholder region created for {img} -> {rdir}/region-1.json")


def main():
    ap = argparse.ArgumentParser(description="Detect regions using GroundedDINO + SAM/SAM2 (requires installed models)")
    ap.add_argument("--images", nargs="+", help="Page/Frame images (PNG)")
    ap.add_argument("--outdir", default="out/visual/grounded_regions", help="Output root folder")
    ap.add_argument("--grounding-model", default=os.getenv("GROUNDING_MODEL", ""), help="Path to GroundingDINO weights")
    ap.add_argument("--sam-model", default=os.getenv("SAM_MODEL", ""), help="Path to SAM/SAM2 weights")
    ap.add_argument("--prompts", nargs="*", default=["diagram", "table", "canvas", "legend", "node", "arrow"], help="Text prompts for GroundingDINO")
    args = ap.parse_args()

    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)

    # Check packages; print clear guidance if missing
    try:
        require_packages()
    except SystemExit as e:
        print(str(e))
        print("Proceeding with placeholder full-image region output so downstream can be tested.")

    images = [Path(p) for p in args.images]
    detect_regions_with_grounded(images, out, args.grounding_model, args.sam_model, args.prompts)


if __name__ == "__main__":
    main()

