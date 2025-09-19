#!/usr/bin/env python3
import argparse
import html
import json
from pathlib import Path


def collect_regions(root: Path, min_score: float = 0.0, tier: str = ""):
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
            auto_tier = None
            auto_score = None
            scoring = None
            if struct.exists():
                try:
                    obj = json.loads(struct.read_text())
                    struct_type = obj.get("artifact_type")
                    tg = obj.get("Tagging") or {}
                    if isinstance(tg, dict):
                        auto_tier = tg.get("AutoTier")
                        auto_score = tg.get("AutoScore")
                    scoring = obj.get("Scoring") or {}
                except Exception:
                    pass
            facts = list((rdir).glob(f"region-{rid}.facts.jsonl"))
            png = rdir / f"region-{rid}.png"
            # filter by score/tier if requested
            if auto_score is not None and auto_score < min_score:
                continue
            if tier and (str(auto_tier or "").lower() != tier.lower()):
                continue
            regions.append({
                "rid": rid,
                "caption": caption,
                "struct_type": struct_type,
                "auto_tier": auto_tier,
                "auto_score": auto_score,
                "scoring": scoring,
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


def render_html(out: Path, datasets, inline_images: bool = False, auto_refresh: int = 0):
    with open(out, "w", encoding="utf-8") as f:
        f.write("<!doctype html><meta charset='utf-8'><title>Visual Review</title>")
        if auto_refresh and auto_refresh > 0:
            f.write(f"<meta http-equiv='refresh' content='{int(auto_refresh)}'>")
        f.write("<style>body{font-family:sans-serif} .grid{display:grid;grid-template-columns:320px 1fr;gap:16px;margin:16px 0;border-top:1px solid #ddd;padding-top:16px} img{max-width:300px;border:1px solid #ccc} .meta{color:#555;font-size:12px} .cap{margin:8px 0} .summary{margin:8px 0;padding:6px 8px;background:#f7f7f7;border:1px solid #e3e3e3;display:inline-block}</style>")
        f.write("<h1>Visual Review</h1>")
        for title, pages in datasets:
            if not pages:
                continue
            f.write(f"<h2>{html.escape(title)}</h2>")
            # Summary across all regions
            total = 0
            tier_counts = {"Major": 0, "Secondary": 0, "Hint": 0, "None": 0}
            for page in pages.values():
                for r in page:
                    total += 1
                    t = (r.get('auto_tier') or 'None')
                    tier_counts[t] = tier_counts.get(t, 0) + 1
            if total > 0:
                f.write("<div class='summary'>")
                f.write(f"Total regions: {total} | ")
                f.write(" | ".join([f"{k}: {v}" for k, v in tier_counts.items()]))
                f.write("</div>")
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
                    # scoring summary
                    sc = r.get('scoring') or {}
                    tier = r.get('auto_tier')
                    score = r.get('auto_score')
                    if sc or tier or score is not None:
                        s1 = sc.get('signals', {}).get('s1_dino')
                        s2 = sc.get('signals', {}).get('s2_sam2')
                        s3 = sc.get('signals', {}).get('s3_text')
                        s4 = sc.get('signals', {}).get('s4_layout')
                        prof = sc.get('profile')
                        conf = sc.get('confidence_visual')
                        fweight = sc.get('final_weight')
                        f.write("<div class='meta'>")
                        f.write(f"profile={html.escape(str(prof))} | tier={html.escape(str(tier))} | score={html.escape(str(score))}")
                        f.write("</div>")
                        f.write("<div class='meta'>")
                        f.write(f"s1={s1} s2={s2} s3={s3} s4={s4} | conf={conf} | final={fweight}")
                        f.write("</div>")
                    f.write(f"<div class='cap'>{html.escape(r.get('caption') or '')}</div>")
                    if r.get("facts_path"):
                        f.write(f"<div class='meta'>facts: {html.escape(r['facts_path'])}</div>")
                    f.write("</div></div>")
        print(f"Wrote {out}")


def main():
    ap = argparse.ArgumentParser(description="Generate an HTML review of visual regions (images+captions+struct)")
    ap.add_argument("--out", default="eval/visual_review.html")
    ap.add_argument("--pages-dir", default="out/visual/playbook")
    ap.add_argument("--regions-detect", default="out/visual/grounded_regions",
                    help="Directory with grounded (non-CV) detected regions: <unit>/regions/region-*.json")
    ap.add_argument("--inline", action="store_true", help="Embed images into HTML as base64 to make it self-contained")
    ap.add_argument("--auto-refresh", type=int, default=0, help="Add meta refresh tag (seconds) for live updates")
    ap.add_argument("--min-score", type=float, default=0.0, help="Filter regions with AutoScore below this value")
    ap.add_argument("--tier", default="", choices=["", "Major", "Secondary", "Hint"], help="Filter by AutoTier")
    args = ap.parse_args()

    # Only grounded/true detected regions are shown; CV is deprecated
    reg_detect = collect_regions(Path(args.regions_detect), min_score=args.min_score, tier=args.tier)
    render_html(Path(args.out), [("Detected Regions (Grounded)", reg_detect)], inline_images=args.inline, auto_refresh=args.auto_refresh)


if __name__ == "__main__":
    main()
