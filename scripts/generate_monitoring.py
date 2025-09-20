#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


def pct(a: int, b: int) -> float:
    return (100.0 * a / b) if b else 0.0


def compute_page_stats(unified_root: str, portal_idx: dict | None = None) -> dict:
    root = Path(unified_root)
    if not root.exists():
        return {"pages_total": 0, "pages_ge50": 0, "pages_lt50": 0, "below": []}
    # Optional map slug -> title
    slug2title = {}
    if portal_idx and isinstance(portal_idx, dict):
        for d in portal_idx.get("playbooks", []) or []:
            slug2title[str(d.get("slug"))] = d.get("title") or d.get("slug")
    below: list[tuple[str, str, int, str]] = []  # (slug, id, count, title)
    pages_total = 0
    pages_ge50 = 0
    for slug_dir in sorted([p for p in root.iterdir() if p.is_dir()], key=lambda p: p.name):
        slug = slug_dir.name
        title = slug2title.get(slug, slug)
        for item_dir in sorted([p for p in slug_dir.iterdir() if p.is_dir()]):
            pid = item_dir.name
            if not pid.startswith("p"):
                continue
            pages_total += 1
            cnt = 0
            agg = item_dir / "regions.json"
            if agg.exists():
                try:
                    js = json.loads(agg.read_text(encoding="utf-8"))
                    regs = js.get("regions") or []
                    cnt = int(js.get("count") or len(regs))
                except Exception:
                    cnt = 0
            if cnt >= 50:
                pages_ge50 += 1
            else:
                below.append((slug, pid, cnt, title))
    pages_lt50 = len(below)
    below.sort(key=lambda t: t[2])
    return {
        "pages_total": pages_total,
        "pages_ge50": pages_ge50,
        "pages_lt50": pages_lt50,
        "below": below[:50],
    }


def render(metrics: dict, coverage: dict, trends: dict | None = None, page_stats: dict | None = None) -> str:
    g = metrics.get("global", {})
    docs = metrics.get("documents", [])
    # sort by ilevel asc to surface weakest first
    docs2 = sorted(docs, key=lambda d: (d.get("ilevel") or 0.0, d.get("slug")))
    # progress
    p_total = int(g.get("pages_total") or 0) + int(g.get("frames_total") or 0)
    p_done = int(g.get("pages_done") or 0) + int(g.get("frames_done") or 0)
    r_total = int(g.get("regions_total") or 0)
    r_an = int(g.get("analyzed_regions") or 0)
    # Optional trends block
    trends_html = ""
    if trends and trends.get("count", 0) >= 2:
        def sparkline(vals, width=280, height=40, pad=4, color="#3b82f6"):
            try:
                vs = [float(v) for v in vals]
                if not vs:
                    return ""
                vmin = min(vs)
                vmax = max(vs)
                rng = (vmax - vmin) or 1.0
                pts = []
                n = len(vs)
                for i, v in enumerate(vs):
                    x = pad + (width - 2*pad) * (i / max(1, n - 1))
                    y = pad + (height - 2*pad) * (1.0 - (v - vmin) / rng)
                    pts.append(f"{x:.1f},{y:.1f}")
                path = " ".join(pts)
                return f"<svg width='{width}' height='{height}' viewBox='0 0 {width} {height}'><polyline fill='none' stroke='{color}' stroke-width='2' points='{path}'/></svg>"
            except Exception:
                return ""
        trends_html = (
            "<div class='card'>"
            "<div class='muted'>Trends</div>"
            f"<div>I‑Level</div>{sparkline(trends.get('ilevel') or [])}"
            f"<div style='margin-top:6px'>Analysis coverage</div>{sparkline(trends.get('analysis') or [], color='#10b981')}"
            f"<div class='muted' style='margin-top:8px'>Alerts: {html.escape('; '.join(trends.get('alerts') or []) or '—')}</div>"
            "</div>"
        )

    # Optional page >=50 widget
    page_html = ""
    if page_stats and page_stats.get("pages_total", 0):
        pt = int(page_stats.get("pages_total") or 0)
        pge = int(page_stats.get("pages_ge50") or 0)
        plt = int(page_stats.get("pages_lt50") or 0)
        pct50 = pct(pge, pt)
        page_html = (
            "<div class='card'>"
            f"<div class='name'>Pages ≥50 / total</div><div class='val'>{pge}/{pt} ({pct50:.1f}%)</div>"
            f"<div class='name' style='margin-top:8px'>Pages &lt;50: {plt}</div>"
            "</div>"
        )

    # CTA to re-run low pages
    cmd = "python3 scripts/rerun_low_regions.py --threshold 50"
    cta_html = (
        "<div class='card' style='margin-top:16px'>"
        "<div class='name'>Action — Re-run low pages (tiled)</div>"
        f"<div>Command: <code>{html.escape(cmd)}</code></div>"
        "<button id='btn-copy-rerun' class='btn' style='margin-top:6px'>Copy command</button>"
        "<div class='muted' style='margin-top:6px'>Adjust threshold if needed. Uses multi-grid & multi-scale GroundedDINO.</div>"
        "</div>"
    )

    return (
        "<!doctype html><meta charset='utf-8'><title>Monitoring</title>"
        "<meta http-equiv='refresh' content='10'>"
        "<style>body{font-family:system-ui,Arial,sans-serif;max-width:1040px;margin:24px auto;line-height:1.45}" \
        ".kpis{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:12px;margin:12px 0}" \
        ".card{border:1px solid #e5e7eb;border-radius:8px;padding:12px;background:#fff}" \
        ".name{font-size:12px;color:#6b7280;text-transform:uppercase;letter-spacing:.02em}" \
        ".val{font-size:22px;font-weight:700}" \
        ".bar{height:10px;background:#f3f4f6;border-radius:6px;overflow:hidden}" \
        ".bar>div{height:10px;background:#3b82f6}" \
        "table{border-collapse:collapse;width:100%;margin-top:16px}" \
        "th,td{border:1px solid #e5e7eb;padding:6px 8px;font-size:14px;text-align:left}" \
        "th{background:#f8fafc}" \
        "a{color:#0a63c5;text-decoration:none} a:hover{text-decoration:underline}"
        "</style>"
        "<h1>Monitoring — Coverage & Readiness (Phase 1)</h1>"
        "<div class='kpis'>"
        f"<div class='card'><div class='name'>Docs</div><div class='val'>{int(g.get('docs') or 0)}</div></div>"
        f"<div class='card'><div class='name'>Pages</div><div class='val'>{int(g.get('pages_done') or 0)}/{int(g.get('pages_total') or 0)}</div></div>"
        f"<div class='card'><div class='name'>Frames</div><div class='val'>{int(g.get('frames_done') or 0)}/{int(g.get('frames_total') or 0)}</div></div>"
        f"<div class='card'><div class='name'>Regions (total)</div><div class='val'>{int(g.get('regions_total') or 0)}</div></div>"
        f"<div class='card'><div class='name'>Analyzed regions</div><div class='val'>{int(g.get('analyzed_regions') or 0)}</div></div>"
        f"<div class='card'><div class='name'>Index lines</div><div class='val'>{int(g.get('index_lines') or 0)}</div></div>"
        f"<div class='card'><div class='name'>I-Level (heuristic)</div><div class='val'>{(g.get('ilevel') or 0):.2f}</div></div>"
        + page_html +
        "</div>"
        "<div class='card'>"
        f"<div class='name'>Render coverage: {pct(p_done, p_total):.1f}%</div>"
        f"<div class='bar'><div style='width:{pct(p_done, p_total):.1f}%' ></div></div>"
        f"<div class='name' style='margin-top:8px'>Analysis coverage: {pct(r_an, r_total):.1f}%</div>"
        f"<div class='bar'><div style='width:{pct(r_an, r_total):.1f}%' ></div></div>"
        "</div>"
        + trends_html +
        "<h2>Documents</h2>"
        "<table>"
        "<tr><th>Title</th><th>Pages</th><th>Done</th><th>Coverage %</th><th>Overlays</th><th>I-Level</th><th>RL</th><th>Unmet</th></tr>"
    + "".join(
        f"<tr><td>{html.escape(d.get('title') or d.get('slug') or '')}</td>"
        f"<td>{d.get('coverage',{}).get('pages_total',0)}</td>"
        f"<td>{d.get('coverage',{}).get('pages_done',0)}</td>"
        f"<td>{pct(d.get('coverage',{}).get('pages_done',0), d.get('coverage',{}).get('pages_total',0)):.1f}</td>"
        f"<td>{d.get('coverage',{}).get('overlays',0)}</td>"
        f"<td>{(d.get('ilevel') or 0):.2f}</td>"
        f"<td>{html.escape(str(d.get('rl') or ''))}</td>"
        f"<td>{html.escape(','.join(d.get('unmet') or []))}</td></tr>"
        for d in docs2
      )
    + "</table>"
      "<p style='margin-top:16px'>"
      "Links: "
      "<a href='../index.html'>Portal Home</a> · "
      "<a href='../readiness/index.html'>Readiness</a> · "
      "<a id='lnk-progress' href='#' target='_blank'>Eval/Progress</a> · "
      "<a id='lnk-review' href='#' target='_blank'>Visual Review</a>"
      "</p>"
      "<script>(function(){try{var h=location.hostname||'localhost';var p=location.port||'8000';var ep='8001';if(p && p!=='' && p!=='80'){ep='8001';}var base='http://'+h+':'+ep+'/';var e1=document.getElementById('lnk-progress'); if(e1) e1.href=base+'progress.html'; var e2=document.getElementById('lnk-review'); if(e2) e2.href=base+'visual_review.html'; var b=document.getElementById('btn-copy-rerun'); if(b && navigator.clipboard){ var cmd=\"" + html.escape(cmd).replace("\\","\\\\").replace("\"","\\\"") + "\"; b.addEventListener('click', function(){ navigator.clipboard.writeText(cmd).then(function(){ b.textContent='Copied!'; setTimeout(function(){ b.textContent='Copy command'; }, 1500); }); }); } }catch(e){}})();</script>"
      + cta_html
      + ("<div class='card' style='margin-top:16px'><div class='name'>Pages &lt;50 (top 50)</div>" 
         + "<table><tr><th>Document</th><th>Page</th><th>Count</th></tr>" 
         + "".join([f"<tr><td>{html.escape(t)}</td><td>{html.escape(slug + '/' + pid)}</td><td>{c}</td></tr>" for (slug,pid,c,t) in (page_stats.get('below') if page_stats else [])]) 
         + "</table></div>" if page_stats and page_stats.get('below') else "")
    )


def main():
    ap = argparse.ArgumentParser(description="Generate monitoring HTML page from metrics.json (Phase 1)")
    ap.add_argument("--metrics", default="out/portal/metrics.json")
    ap.add_argument("--coverage", default="out/portal/coverage.json")
    ap.add_argument("--out", default="out/portal/monitoring/index.html")
    ap.add_argument("--trends", default="out/portal/metrics_trends.json")
    ap.add_argument("--unified-root", default="out/visual/regions/gdino_sam2")
    args = ap.parse_args()

    metrics = json.loads(Path(args.metrics).read_text(encoding="utf-8"))
    coverage = json.loads(Path(args.coverage).read_text(encoding="utf-8"))
    t = None
    try:
        p = Path(args.trends)
        if p.exists():
            t = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        t = None
    portal_idx = None
    try:
        pi = Path("out/portal/portal_index.json")
        if pi.exists():
            portal_idx = json.loads(pi.read_text(encoding="utf-8"))
    except Exception:
        portal_idx = None
    ps = compute_page_stats(args.unified_root, portal_idx=portal_idx)
    html_out = render(metrics, coverage, trends=t, page_stats=ps)
    outp = Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(html_out, encoding="utf-8")
    print(f"Wrote {outp}")


if __name__ == "__main__":
    main()
