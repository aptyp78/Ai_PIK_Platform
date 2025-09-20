#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, Any, List, Tuple


def slugify(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s or "doc"


def title_by_slug(pages_root: Path, frames_root: Path) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for root in [pages_root, frames_root]:
        if not root.exists():
            continue
        for d in root.iterdir():
            if d.is_dir():
                mapping[slugify(d.name)] = d.name
    return mapping


def source_image_for(item_dir: Path, titles: Dict[str, str]) -> Path | None:
    # item_dir: out/visual/regions/gdino_sam2/<slug>/<pNNN|fNNNN>
    slug = item_dir.parent.name
    item = item_dir.name
    title = titles.get(slug)
    if not title:
        return None
    if item.startswith("p"):
        try:
            n = int(item[1:])
        except Exception:
            return None
        p = Path("out/page_images") / title / f"page-{n}.png"
        return p if p.exists() else None
    if item.startswith("f"):
        p = Path("out/frame_images") / title / f"{item}.png"
        return p if p.exists() else None
    return None


def color_for(reg: Dict[str, Any]) -> Tuple[int, int, int]:
    tier = (reg.get("Tagging", {}) or {}).get("AutoTier") or (reg.get("auto_tier") or "")
    t = (str(tier) or "").lower()
    if t == "major":
        return (220, 38, 38)  # red
    if t == "secondary":
        return (234, 179, 8)  # amber
    if t == "hint":
        return (37, 99, 235)  # blue
    # by type
    tp = (reg.get("struct_type") or reg.get("type") or "").lower()
    if tp == "table":
        return (16, 185, 129)  # green
    if tp == "canvas":
        return (99, 102, 241)  # indigo
    if tp == "diagram":
        return (59, 130, 246)  # blue
    return (239, 68, 68)


def draw_overlay(item_dir: Path, src: Path) -> bool:
    agg = item_dir / "regions.json"
    if not agg.exists():
        return False
    try:
        from PIL import Image, ImageDraw
        try:
            Image.MAX_IMAGE_PIXELS = 3_000_000_000  # allow very large pages
        except Exception:
            pass
    except Exception:
        return False
    try:
        regs = json.loads(agg.read_text(encoding="utf-8")).get("regions") or []
    except Exception:
        regs = []
    if not regs:
        return False
    im = Image.open(src).convert("RGB")
    draw = ImageDraw.Draw(im)
    for r in regs:
        bb = r.get("bbox")
        if not bb or not isinstance(bb, (list, tuple)) or len(bb) != 4:
            continue
        x, y, w, h = bb
        x2, y2 = x + w, y + h
        color = color_for(r)
        # thicker for Major/Secondary
        tier = (r.get("Tagging", {}) or {}).get("AutoTier") or (r.get("auto_tier") or "")
        t = str(tier).lower()
        width = 3
        if t == "major":
            width = 5
        elif t == "secondary":
            width = 4
        draw.rectangle([x, y, x2, y2], outline=color, width=width)
    out = item_dir / "overlay.png"
    im.save(out)
    return True


def process_all(root: Path) -> Tuple[int, int]:
    pages_root = Path("out/page_images")
    frames_root = Path("out/frame_images")
    titles = title_by_slug(pages_root, frames_root)
    total = 0
    done = 0
    for slug_dir in sorted([p for p in root.iterdir() if p.is_dir()], key=lambda p: p.name):
        for item_dir in sorted([p for p in slug_dir.iterdir() if p.is_dir()]):
            total += 1
            src = source_image_for(item_dir, titles)
            if not src:
                continue
            if draw_overlay(item_dir, src):
                done += 1
    return total, done


def main():
    ap = argparse.ArgumentParser(description="Generate overlay.png for unified regions (gdino_sam2)")
    ap.add_argument("--root", default="out/visual/regions/gdino_sam2")
    args = ap.parse_args()
    root = Path(args.root)
    if not root.exists():
        print(f"no root: {root}")
        return
    total, done = process_all(root)
    print(f"Items: {total}; overlays written: {done}")


if __name__ == "__main__":
    main()
