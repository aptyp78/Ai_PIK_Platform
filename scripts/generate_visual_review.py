#!/usr/bin/env python3
import argparse
import html
import json
from pathlib import Path


def collect_regions(root: Path):
    pages = {}
    if not root.exists():
        return pages
    for pdir in sorted([d for d in root.iterdir() if d.is_dir() and d.name.isdigit()], key=lambda d: int(d.name)):
        page = int(pdir.name)
        rdir = pdir / "regions"
        if not rdir.exists():
            continue
        regions = []
        # avoid matching files like region-1.caption.txt by parsing properly
        for cap in sorted(rdir.glob("region-*.caption.txt")):
            stem = cap.stem  # e.g., region-1.caption
            try:
                rid = int(stem.split("-")[-1].split(".")[0])
            except Exception:
                continue
            caption = cap.read_text(encoding="utf-8").strip()
            struct = (rdir / f"region-{rid}.struct.json")
            struct_type = None
            if struct.exists():
                try:
                    obj = json.loads(struct.read_text())
                    struct_type = obj.get("artifact_type")
                except Exception:
                    pass
            facts = list((rdir).glob(f"region-{rid}.facts.jsonl"))
            png = rdir / f"region-{rid}.png"
            regions.append({
                "rid": rid,
                "caption": caption,
                "struct_type": struct_type,
                "facts_path": str(facts[0]) if facts else None,
                "png_path": str(png) if png.exists() else None,
            })
        if regions:
            pages[page] = regions
    return pages


def _img_tag(path: str, inline: bool) -> str:
    if not inline:
        return f"<img src='{html.escape(path)}'/>"
    try:
        import base64
        data = Path(path).read_bytes()
        b64 = base64.b64encode(data).decode("utf-8")
        return f"<img src='data:image/png;base64,{b64}'/>"
    except Exception:
        return "<div class='meta'>(image unavailable)</div>"


def render_html(out: Path, datasets, inline_images: bool = False):
    with open(out, "w", encoding="utf-8") as f:
        f.write("<!doctype html><meta charset='utf-8'><title>Visual Review</title>")
        f.write("<style>body{font-family:sans-serif} .grid{display:grid;grid-template-columns:320px 1fr;gap:16px;margin:16px 0;border-top:1px solid #ddd;padding-top:16px} img{max-width:300px;border:1px solid #ccc} .meta{color:#555;font-size:12px} .cap{margin:8px 0}</style>")
        f.write("<h1>Visual Review</h1>")
        for title, pages in datasets:
            if not pages:
                continue
            f.write(f"<h2>{html.escape(title)}</h2>")
            for page in sorted(pages.keys()):
                f.write(f"<h3>Page {page}</h3>")
                for r in pages[page]:
                    f.write("<div class='grid'>")
                    if r.get("png_path"):
                        f.write("<div>")
                        f.write(_img_tag(r["png_path"], inline_images))
                        f.write(f"<div class='meta'>{html.escape(r['png_path'])}</div></div>")
                    else:
                        f.write("<div><div class='meta'>(no image)</div></div>")
                    f.write("<div>")
                    f.write(f"<div class='meta'>region-{r['rid']} | struct={html.escape(str(r.get('struct_type') or ''))}</div>")
                    f.write(f"<div class='cap'>{html.escape(r.get('caption') or '')}</div>")
                    if r.get("facts_path"):
                        f.write(f"<div class='meta'>facts: {html.escape(r['facts_path'])}</div>")
                    f.write("</div></div>")
        print(f"Wrote {out}")


def main():
    ap = argparse.ArgumentParser(description="Generate an HTML review of visual regions (images+captions+struct)")
    ap.add_argument("--out", default="eval/visual_review.html")
    ap.add_argument("--pages-dir", default="out/visual/playbook")
    ap.add_argument("--regions-detect", default="out/visual/regions_detect")
    ap.add_argument("--regions-cv", default="out/visual/cv_regions")
    ap.add_argument("--regions-frames", default="out/visual/cv_frames")
    ap.add_argument("--inline", action="store_true", help="Embed images into HTML as base64 to make it self-contained")
    args = ap.parse_args()

    pages = collect_regions(Path(args.pages_dir))
    reg_detect = collect_regions(Path(args.regions_detect))
    reg_cv = collect_regions(Path(args.regions_cv))
    reg_frames = collect_regions(Path(args.regions_frames))
    render_html(Path(args.out), [("CV Regions (Playbook)", reg_cv), ("CV Regions (Frames)", reg_frames), ("Detected Regions", reg_detect)], inline_images=args.inline)


if __name__ == "__main__":
    main()
