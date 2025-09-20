#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def slugify(s: str) -> str:
    import unicodedata, re
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s or "doc"


def ensure_thumb(src: Path, thumb: Path, width: int = 320) -> Path:
    try:
        from PIL import Image
    except Exception:
        return src
    thumb.parent.mkdir(parents=True, exist_ok=True)
    try:
        im = Image.open(src)
        w, h = im.size
        if w > width:
            nh = int(h * (width / float(w)))
            im = im.resize((width, nh))
        im.save(thumb)
        return thumb
    except Exception:
        return src


def scan_page_images(root: Path, data: dict) -> None:
    if not root.exists():
        return
    for d in sorted([p for p in root.iterdir() if p.is_dir()], key=lambda p: p.name.lower()):
        files = list(d.glob("*.png"))
        if not files:
            continue
        title = d.name
        slug = slugify(title)
        # Detect kind by filename pattern
        pages = sorted(d.glob("page-*.png"), key=lambda p: int(re.search(r"(\d+)", p.stem).group(1)) if re.search(r"(\d+)", p.stem) else 0)
        frames = sorted(d.glob("f*.png"), key=lambda p: int(re.search(r"(\d+)", p.stem).group(1)) if re.search(r"(\d+)", p.stem) else 0)
        if pages:
            items = []
            for p in pages:
                m = re.search(r"(\d+)", p.stem)
                if not m:
                    continue
                pid = f"p{int(m.group(1)):03d}"
                t = Path("out/page_thumbs") / title / f"page-{int(m.group(1))}.png"
                thumb = ensure_thumb(p, t)
                items.append({"id": pid, "source": str(p), "thumb": str(thumb)})
            data["playbooks"].append({
                "title": title,
                "slug": slug,
                "dir": str(d),
                "kind": "playbook",
                "items": items,
                "pages_total": len(items),
            })
        elif frames:
            items = []
            for f in frames:
                m = re.search(r"(\d+)", f.stem)
                if not m:
                    continue
                fid = f"f{int(m.group(1)):04d}"
                t = Path("out/page_thumbs") / title / f"{fid}.png"
                thumb = ensure_thumb(f, t)
                items.append({"id": fid, "source": str(f), "thumb": str(thumb)})
            data["framesets"].append({
                "title": title,
                "slug": slug,
                "dir": str(d),
                "kind": "frame_set",
                "items": items,
                "frames_total": len(items),
            })
    return


def main():
    ap = argparse.ArgumentParser(description="Build unified portal index from out/page_images and thumbs")
    ap.add_argument("--pages-root", default="out/page_images")
    ap.add_argument("--thumbs-root", default="out/page_thumbs")
    ap.add_argument("--out", default="out/portal/portal_index.json")
    args = ap.parse_args()

    root = Path(args.pages_root)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    idx = {"playbooks": [], "framesets": []}
    # Scan playbooks+frames under page_images
    scan_page_images(root, idx)
    # Additionally derive framesets from unified detection (gdino_sam2)
    gd_root = Path("out/visual/regions/gdino_sam2")
    if gd_root.exists():
        for dslug_dir in sorted([p for p in gd_root.iterdir() if p.is_dir()], key=lambda p: p.name):
            # collect fNNNN under this slug
            fitems = []
            title = None
            for item_dir in sorted(dslug_dir.iterdir()):
                name = item_dir.name
                if not re.match(r"f\d{1,}$", name):
                    continue
                fid = name if name.startswith('f') else f"f{int(name):04d}"
                src_overlay = item_dir / "overlay.png"
                # if we know a human title, thumbs dir will use it; otherwise slug
                # read meta for title if exists
                if title is None:
                    meta = item_dir / "meta.json"
                    if meta.exists():
                        try:
                            js = json.loads(meta.read_text(encoding='utf-8'))
                            title = js.get('doc_title') or title
                        except Exception:
                            pass
                # fallback title from slug if missing
                if title is None:
                    title = dslug_dir.name
                # Build/copy thumb from overlay if present
                thumb_path = Path("out/page_thumbs") / title / f"{fid}.png"
                src_img = src_overlay if src_overlay.exists() else None
                if src_img and src_img.exists():
                    thumb = ensure_thumb(src_img, thumb_path)
                    fitems.append({"id": fid, "source": str(src_img), "thumb": str(thumb)})
                else:
                    # cannot find source; keep placeholder thumb path
                    fitems.append({"id": fid, "source": "", "thumb": str(thumb_path)})
            if fitems:
                title_eff = title or dslug_dir.name
                fs = {
                    "title": title_eff,
                    "slug": dslug_dir.name,
                    "dir": "",
                    "kind": "frame_set",
                    "items": fitems,
                    "frames_total": len(fitems),
                }
                # avoid duplicates by slug
                if not any(x.get('slug') == fs['slug'] for x in idx['framesets']):
                    idx['framesets'].append(fs)
    out.write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out} with {len(idx['playbooks'])} playbooks and {len(idx['framesets'])} framesets")


if __name__ == "__main__":
    main()

