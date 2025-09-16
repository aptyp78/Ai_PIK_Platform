#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path
from typing import Dict, List, Tuple


def load_existing(out_path: Path) -> Tuple[List[Dict], int]:
    existing = []
    next_id = 0
    if out_path.exists():
        with open(out_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                obj = json.loads(line)
                existing.append(obj)
        if existing:
            next_id = max(int(o.get("id", -1)) for o in existing) + 1
    return existing, next_id


def iter_region_pngs(root: Path) -> List[Tuple[Path, Dict]]:
    out: List[Tuple[Path, Dict]] = []
    # Look for */regions/region-*.png
    if (root / "regions").exists():
        dirs = [root / "regions"]
    else:
        dirs = [p for p in root.glob("*/regions") if p.is_dir()]
    for d in dirs:
        unit = d.parent.name
        page = None
        try:
            page = int(unit)
        except Exception:
            page = None
        for png in sorted(d.glob("region-*.png")):
            try:
                rid = int(png.stem.split("-")[-1])
            except Exception:
                rid = None
            meta = {
                "page": page,
                "region_id": rid,
                "preview": str(png),
                "unit": unit,
            }
            out.append((png, meta))
    return out


def iter_page_pngs(root: Path) -> List[Tuple[Path, Dict]]:
    out: List[Tuple[Path, Dict]] = []
    # Expect structure: out/page_images/<unit>/page-<n>.png
    if not root.exists():
        return out
    for unit_dir in sorted(root.iterdir()):
        if not unit_dir.is_dir():
            continue
        unit = unit_dir.name
        for png in sorted(unit_dir.glob("page-*.png")):
            try:
                page = int(png.stem.split('-')[-1])
            except Exception:
                page = None
            meta = {
                "page": page,
                "region_id": None,
                "preview": str(png),
                "unit": unit,
            }
            out.append((png, meta))
    return out


def encode_images_openclip(paths: List[Path], model_name: str = "ViT-B-32", pretrained: str = "laion2b_s34b_b79k") -> List[List[float]]:
    try:
        import open_clip  # type: ignore
        import torch  # type: ignore
        from PIL import Image  # type: ignore
    except Exception as e:
        raise SystemExit("open_clip/torch/Pillow are required to embed images. pip install open-clip-torch pillow torch")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, _, preprocess = open_clip.create_model_and_transforms(model_name, pretrained=pretrained, device=device)
    model.eval()
    images = []
    for p in paths:
        im = Image.open(p).convert("RGB")
        images.append(preprocess(im))
    batch = torch.stack(images).to(device)
    with torch.no_grad():
        feats = model.encode_image(batch)
        feats = feats / feats.norm(dim=-1, keepdim=True)
    vecs = feats.cpu().tolist()  # type: ignore
    return vecs


def main():
    ap = argparse.ArgumentParser(description="Embed region PNGs with OpenCLIP and append to NDJSON index")
    ap.add_argument("--regions-dir", default="out/visual/grounded_regions")
    ap.add_argument("--out", default="out/openai_embeddings.ndjson")
    ap.add_argument("--model-name", default="ViT-B-32")
    ap.add_argument("--pretrained", default="laion2b_s34b_b79k")
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--pages-dir", default="out/page_images", help="Directory with rendered page PNGs")
    args = ap.parse_args()

    regions_root = Path(args.regions_dir)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    existing, next_id = load_existing(out_path)
    pngs = iter_region_pngs(regions_root)
    # add page images
    pngs += iter_page_pngs(Path(args.pages_dir))
    if not pngs:
        raise SystemExit(f"No region PNGs found under {regions_root}")

    # Encode in batches
    with open(out_path, "a", encoding="utf-8") as f:
        for i in range(0, len(pngs), args.batch):
            batch_paths = [p for p, _ in pngs[i : i + args.batch]]
            batch_meta = [m for _, m in pngs[i : i + args.batch]]
            vecs = encode_images_openclip(batch_paths, model_name=args.model_name, pretrained=args.pretrained)
            for meta, v in zip(batch_meta, vecs):
                rec = {
                    "id": next_id,
                    "text": "",
                    "vector": v,
                    "meta": {
                        "type": "ImageVec",
                        "page": meta.get("page"),
                        "filename": meta.get("unit"),
                        "source_file": str(regions_root),
                        "span": 1,
                        "tags": ["Diagram"],
                        **({"region_id": meta.get("region_id")} if meta.get("region_id") is not None else {}),
                        **({"preview": meta.get("preview")} if meta.get("preview") else {}),
                    },
                    "provider": "open_clip",
                    "model": f"{args.model_name}/{args.pretrained}",
                }
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                next_id += 1

    print(f"Appended {len(pngs)} ImageVec records to {out_path}")


if __name__ == "__main__":
    main()
