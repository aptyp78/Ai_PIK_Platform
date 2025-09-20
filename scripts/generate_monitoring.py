#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


def pct(a: int, b: int) -> float:
    return (100.0 * a / b) if b else 0.0


def render(metrics: dict, coverage: dict) -> str:
    g = metrics.get("global", {})
    docs = metrics.get("documents", [])
    # sort by ilevel asc to surface weakest first
    docs2 = sorted(docs, key=lambda d: (d.get("ilevel") or 0.0, d.get("slug")))
    # progress
    p_total = int(g.get("pages_total") or 0) + int(g.get("frames_total") or 0)
    p_done = int(g.get("pages_done") or 0) + int(g.get("frames_done") or 0)
    r_total = int(g.get("regions_total") or 0)
    r_an = int(g.get("analyzed_regions") or 0)
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
        "</div>"
        "<div class='card'>"
        f"<div class='name'>Render coverage: {pct(p_done, p_total):.1f}%</div>"
        f"<div class='bar'><div style='width:{pct(p_done, p_total):.1f}%' ></div></div>"
        f"<div class='name' style='margin-top:8px'>Analysis coverage: {pct(r_an, r_total):.1f}%</div>"
        f"<div class='bar'><div style='width:{pct(r_an, r_total):.1f}%' ></div></div>"
        "</div>"
        "<h2>Documents</h2>"
        "<table>"
        "<tr><th>Title</th><th>Pages</th><th>Done</th><th>Coverage %</th><th>Overlays</th><th>I-Level</th></tr>"
    + "".join(
        f"<tr><td>{html.escape(d.get('title') or d.get('slug') or '')}</td>"
        f"<td>{d.get('coverage',{}).get('pages_total',0)}</td>"
        f"<td>{d.get('coverage',{}).get('pages_done',0)}</td>"
        f"<td>{pct(d.get('coverage',{}).get('pages_done',0), d.get('coverage',{}).get('pages_total',0)):.1f}</td>"
        f"<td>{d.get('coverage',{}).get('overlays',0)}</td>"
        f"<td>{(d.get('ilevel') or 0):.2f}</td></tr>"
        for d in docs2
      )
    + "</table>"
      "<p style='margin-top:16px'>"
      "Links: "
      "<a href='../index.html'>Portal Home</a> · "
      "<a href='../../eval/progress.html' target='_blank'>Eval/Progress</a> · "
      "<a href='../../eval/visual_review.html' target='_blank'>Visual Review</a>"
      "</p>"
    )


def main():
    ap = argparse.ArgumentParser(description="Generate monitoring HTML page from metrics.json (Phase 1)")
    ap.add_argument("--metrics", default="out/portal/metrics.json")
    ap.add_argument("--coverage", default="out/portal/coverage.json")
    ap.add_argument("--out", default="out/portal/monitoring/index.html")
    args = ap.parse_args()

    metrics = json.loads(Path(args.metrics).read_text(encoding="utf-8"))
    coverage = json.loads(Path(args.coverage).read_text(encoding="utf-8"))
    html_out = render(metrics, coverage)
    outp = Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(html_out, encoding="utf-8")
    print(f"Wrote {outp}")


if __name__ == "__main__":
    main()

