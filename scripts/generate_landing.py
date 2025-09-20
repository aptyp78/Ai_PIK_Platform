#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import os
import random
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple


@dataclass
class Ctx:
    portal_root: Path
    page_images: Path
    page_thumbs: Path
    regions_root: Path
    embeddings_path: Path


def load_json(p: Path, default):
    try:
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def copy_if_exists(src: Path, dst: Path) -> bool:
    try:
        if src.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            return True
    except Exception:
        pass
    return False


def choose_doc_thumbs(ctx: Ctx, portal_idx: dict, limit: int = 8) -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = []
    for d in portal_idx.get("playbooks", [])[: limit * 2]:
        title = d.get("title") or ""
        slug = d.get("slug") or ""
        if not title or not slug:
            continue
        # Prefer thumb if exists; else fallback to page-1.png
        src = ctx.page_thumbs / title / "page-1.png"
        if not src.exists():
            src = ctx.page_images / title / "page-1.png"
        if not src.exists():
            continue
        dst = ctx.portal_root / "assets" / "thumbs" / f"{slug}.png"
        if copy_if_exists(src, dst):
            items.append({"title": title, "slug": slug, "img": str(dst.relative_to(ctx.portal_root))})
        if len(items) >= limit:
            break
    return items


def gather_overlays(ctx: Ctx, limit: int = 8) -> List[Dict[str, str]]:
    cand: List[Tuple[int, Path, str]] = []
    root = ctx.regions_root
    if not root.exists():
        return []
    for slug_dir in sorted([p for p in root.iterdir() if p.is_dir()], key=lambda p: p.name)[:100]:
        for item_dir in sorted([p for p in slug_dir.iterdir() if p.is_dir()]):
            ov = item_dir / "overlay.png"
            if not ov.exists():
                continue
            score = 0
            rj = item_dir / "regions.json"
            if rj.exists():
                try:
                    js = json.loads(rj.read_text(encoding="utf-8"))
                    score = int(js.get("count") or len(js.get("regions") or []))
                except Exception:
                    pass
            cand.append((score, ov, f"{slug_dir.name}/{item_dir.name}"))
    cand.sort(key=lambda x: x[0], reverse=True)
    sel: List[Dict[str, str]] = []
    for score, ov, key in cand[: limit * 2]:
        # copy to assets
        dst = ctx.portal_root / "assets" / "overlays" / (key.replace("/", "_") + ".png")
        if copy_if_exists(ov, dst):
            sel.append({"key": key, "img": str(dst.relative_to(ctx.portal_root)), "score": score})
        if len(sel) >= limit:
            break
    return sel


def compute_scatter(ctx: Ctx, limit: int = 300) -> Dict[str, Any]:
    p = ctx.embeddings_path
    data: List[Dict[str, Any]] = []
    if not p.exists():
        return {"points": [], "note": "embeddings missing"}
    # Reservoir sample up to 'limit'
    try:
        import numpy as np  # type: ignore
    except Exception:
        np = None  # type: ignore

    # Read iteratively to avoid loading entire file into RAM
    total = 0
    sample: List[Dict[str, Any]] = []
    with p.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                js = json.loads(line)
            except Exception:
                continue
            total += 1
            if len(sample) < limit:
                sample.append(js)
            else:
                # reservoir
                j = random.randint(0, total - 1)
                if j < limit:
                    sample[j] = js

    if not sample:
        return {"points": [], "note": "no data"}
    # Vectors -> matrix
    try:
        vecs = [s.get("vector") for s in sample if isinstance(s.get("vector"), list)]
        n = len(vecs)
        d = len(vecs[0]) if vecs else 0
        if np is None or d == 0:
            # Fallback: map to random into 2D reproducibly
            random.seed(42)
            pts = [(random.random(), random.random()) for _ in vecs]
        else:
            X = np.array(vecs, dtype=float)
            # PCA 2D
            X = X - X.mean(axis=0)
            U, S, Vt = np.linalg.svd(X, full_matrices=False)
            Z = np.dot(X, Vt[:2].T)
            pts = [(float(Z[i, 0]), float(Z[i, 1])) for i in range(Z.shape[0])]
        # Normalize to 0..1
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        xmin, xmax = min(xs), max(xs)
        ymin, ymax = min(ys), max(ys)
        rx = max(xmax - xmin, 1e-6)
        ry = max(ymax - ymin, 1e-6)
        norm = [((x - xmin) / rx, (y - ymin) / ry) for x, y in pts]
        points: List[Dict[str, Any]] = []
        for i, s in enumerate(sample):
            meta = s.get("meta") or {}
            text = (s.get("text") or "").strip()
            t = (meta.get("type") or "").strip() or "Text"
            tags = meta.get("tags") or []
            points.append({
                "x": round(norm[i][0], 4),
                "y": round(norm[i][1], 4),
                "type": t,
                "tags": tags,
                "text": text[:240],
            })
        return {"points": points, "note": f"sample={len(points)} total~{total}"}
    except Exception as e:
        return {"points": [], "note": f"error: {e}"}


def render_html(ctx: Ctx, metrics: dict, thumbs: List[Dict[str, str]], overlays: List[Dict[str, str]], scatter: Dict[str, Any]) -> str:
    g = metrics.get("global", {})
    kpi = [
        ("Documents", int(g.get("docs") or 0)),
        ("Pages", f"{int(g.get('pages_done') or 0)}/{int(g.get('pages_total') or 0)}"),
        ("Regions", int(g.get("regions_total") or 0)),
        ("Analyzed", int(g.get("analyzed_regions") or 0)),
        ("I‑Level", f"{float(g.get('ilevel') or 0.0):.2f}"),
    ]
    # Basic CSS + sections
    css = """
<style>
body{font-family:system-ui,Arial,sans-serif;margin:0;color:#0f172a;line-height:1.5}
.hero{padding:64px 24px;background:linear-gradient(135deg,#0ea5e9,#6366f1);color:#fff;text-align:center}
.hero h1{margin:0;font-size:44px}
.hero p{margin:12px auto;max-width:820px;font-size:18px;opacity:.95}
.cta{margin-top:18px;display:flex;gap:12px;justify-content:center}
.btn{display:inline-block;padding:12px 18px;border-radius:10px;border:2px solid #fff;color:#0f172a;background:#fff;font-weight:700}
.btn.secondary{background:transparent;color:#fff;border-color:#dbeafe}
.sec{padding:24px 24px}
.h{font-weight:800;margin:8px 0 12px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px}
.card{border:1px solid #e5e7eb;border-radius:12px;padding:12px;background:#fff}
.muted{color:#64748b;font-size:12px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px}
.thumb{width:100%;height:140px;object-fit:cover;border:1px solid #e5e7eb;border-radius:8px;background:#f8fafc}
.overlay{width:100%;height:180px;object-fit:cover;border:1px solid #e5e7eb;border-radius:8px;background:#f8fafc}
.links{display:flex;gap:10px;flex-wrap:wrap}
.tag{display:inline-block;padding:2px 8px;background:#eef2ff;color:#3730a3;border-radius:999px;font-size:12px}
.scatter{border:1px solid #e5e7eb;border-radius:12px;padding:8px;background:#fff}
.footer{padding:24px 24px;color:#64748b}
a{color:#0a63c5;text-decoration:none}
</style>
"""
    # Thumbs grid
    thumbs_html = "".join([
        f"<div class='card'><img class='thumb' src='{t['img']}' loading='lazy'><div class='muted'>{t['title']}</div></div>"
        for t in thumbs
    ])
    # Overlays grid
    overlays_html = "".join([
        f"<div class='card'><img class='overlay' src='{o['img']}' loading='lazy'><div class='muted'>{o['key']} · regions={o['score']}</div></div>"
        for o in overlays
    ])
    # Scatter SVG
    pts = scatter.get("points") or []
    svg_w, svg_h, pad = 860, 420, 12
    def color_for(t: str) -> str:
        t = (t or "").lower()
        return {
            "visualfact": "#0ea5e9",
            "visualcaption": "#6366f1",
            "image": "#f59e0b",
            "table": "#10b981",
            "text": "#6b7280",
        }.get(t, "#64748b")
    circles = []
    tooltips = []
    for i, p in enumerate(pts):
        x = pad + p.get("x", 0) * (svg_w - 2 * pad)
        y = pad + (1 - p.get("y", 0)) * (svg_h - 2 * pad)
        c = color_for(p.get("type"))
        circles.append(f"<circle cx='{x:.1f}' cy='{y:.1f}' r='3' fill='{c}' data-i='{i}' />")
        safe = html_escape(p.get("text") or "")
        tooltips.append(safe)
    scatter_html = (
        f"<div class='scatter'><svg id='sc' width='{svg_w}' height='{svg_h}' viewBox='0 0 {svg_w} {svg_h}' style='max-width:100%'>"
        + "".join(circles)
        + "</svg><div class='muted' style='margin-top:6px'>"
        + html_escape(scatter.get("note") or "")
        + "</div></div>"
    )
    # Script for tooltips
    script = (
        "<script>(function(){var tips="
        + json.dumps(tooltips).replace("</", "<\/")
        + ";var sc=document.getElementById('sc'); if(!sc) return;\n"
          "var tt=document.createElement('div'); tt.style.position='fixed'; tt.style.pointerEvents='none'; tt.style.background='rgba(15,23,42,.96)'; tt.style.color='#fff'; tt.style.padding='8px 10px'; tt.style.borderRadius='8px'; tt.style.maxWidth='360px'; tt.style.fontSize='13px'; tt.style.display='none'; document.body.appendChild(tt);\n"
          "sc.addEventListener('mousemove', function(e){var t=e.target; if(t && t.tagName==='circle' || t.tagName==='CIRCLE'){var i=t.getAttribute('data-i'); if(i){ tt.textContent=tips[i]||''; tt.style.left=(e.clientX+12)+'px'; tt.style.top=(e.clientY+12)+'px'; tt.style.display='block'; }} else {tt.style.display='none';}});\n"
        "})();</script>"
    )

    # KPIs grid
    kpi_html = "".join([f"<div class='card'><div class='muted'>{k}</div><div style='font-size:28px;font-weight:800'>{v}</div></div>" for k, v in kpi])

    return (
        "<!doctype html><meta charset='utf-8'><title>Platform Innovation Kit — Landing</title>"
        + css
        + "<div class='hero'><h1>Platform Innovation Kit</h1>"
          "<p>Обзор методологии и визуальных артефактов PIK с нашими результатами парсинга: страницы, регионы, подписи, факты и метрики качества.</p>"
          "<div class='cta'><a class='btn' href='../playbooks/index.html'>К материалам</a><a class='btn secondary' href='../monitoring/index.html'>Мониторинг</a><a class='btn secondary' href='../readiness/index.html'>Readiness</a></div>"
        "</div>"
        + "<div class='sec'><div class='h'>Ключевые метрики</div><div class='kpis'>" + kpi_html + "</div></div>"
        + "<div class='sec'><div class='h'>Что внутри PIK</div><div class='grid'>" + thumbs_html + "</div></div>"
        + "<div class='sec'><div class='h'>Карта тем (эмбеддинги)</div>" + scatter_html + script + "</div>"
        + "<div class='sec'><div class='h'>Хайлайты (оверлеи)</div><div class='grid'>" + overlays_html + "</div></div>"
        + "<div class='footer'>Сгенерировано локально. Данные: portal_index.json, metrics.json, embeddings.ndjson, overlays.</div>"
    )


def html_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\"", "&quot;")
        .replace("'", "&#39;")
    )


def main():
    ap = argparse.ArgumentParser(description="Generate a landing page for Platform Innovation Kit using local artifacts")
    ap.add_argument("--out", default="out/portal/landing/index.html")
    ap.add_argument("--portal-root", default="out/portal")
    ap.add_argument("--page-images", default="out/page_images")
    ap.add_argument("--page-thumbs", default="out/page_thumbs")
    ap.add_argument("--regions-root", default="out/visual/regions/gdino_sam2")
    ap.add_argument("--embeddings", default="out/openai_embeddings.ndjson")
    ap.add_argument("--redirect-index", action="store_true", help="Replace out/portal/index.html with redirect to landing")
    args = ap.parse_args()

    ctx = Ctx(
        portal_root=Path(args.portal_root),
        page_images=Path(args.page_images),
        page_thumbs=Path(args.page_thumbs),
        regions_root=Path(args.regions_root),
        embeddings_path=Path(args.embeddings),
    )

    portal_idx = load_json(ctx.portal_root / "portal_index.json", default={"playbooks": [], "framesets": []})
    metrics = load_json(ctx.portal_root / "metrics.json", default={"global": {}})

    thumbs = choose_doc_thumbs(ctx, portal_idx, limit=8)
    overlays = gather_overlays(ctx, limit=8)
    scatter = compute_scatter(ctx, limit=300)

    html = render_html(ctx, metrics, thumbs, overlays, scatter)

    outp = Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(html, encoding="utf-8")
    print(f"Wrote {outp}")

    if args.redirect_index:
        idx = ctx.portal_root / "index.html"
        try:
            redir = "<!doctype html><meta charset='utf-8'><meta http-equiv='refresh' content='0;url=landing/index.html'>"
            idx.write_text(rescue_existing_index(idx, redir), encoding="utf-8")
            print(f"Updated {idx} to redirect to landing.")
        except Exception:
            pass


def rescue_existing_index(idx: Path, new_content: str) -> str:
    try:
        old = idx.read_text(encoding="utf-8")
        # Keep a comment with a snippet of the old title to help troubleshooting
        m = re.search(r"<title>([^<]{0,80})", old, flags=re.IGNORECASE)
        title = m.group(1) if m else ""
        return f"<!-- previous index title: {html_escape(title)} -->\n" + new_content
    except Exception:
        return new_content


if __name__ == "__main__":
    main()

