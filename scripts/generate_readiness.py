#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Dict, Any, List, Tuple


def load_json(p: Path, default):
    try:
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def load_readiness_policy(path: Path) -> dict:
    default = {
        "levels": {
            "RL0": {"min_ilevel": 0.0, "min_coverage": 0.0},
            "RL1": {"min_ilevel": 0.50, "min_coverage": 0.50, "min_analyzed_ratio": 0.60, "min_major_secondary_share": 0.25, "min_index_lines": 500},
            "RL2": {"min_ilevel": 0.70, "min_coverage": 0.70, "min_analyzed_ratio": 0.80, "min_median_final_weight": 0.60, "min_known_types": 0.70, "min_index_lines": 2000},
            "RL3": {"min_ilevel": 0.85, "min_coverage": 0.95},
        },
    }
    try:
        import yaml  # type: ignore
        if path.exists():
            return yaml.safe_load(path.read_text(encoding="utf-8")) or default
    except Exception:
        pass
    return default


def pct(a: float, b: float) -> float:
    return (100.0 * a / b) if b else 0.0


def safe_ratio(a: float, b: float) -> float:
    return float(a) / float(b) if b else 0.0


def evaluate_readiness(policy: Dict[str, Any], vals: Dict[str, float]) -> Tuple[str, List[str]]:
    levels = (policy.get("levels") or {})
    order = ["RL3", "RL2", "RL1", "RL0"]
    for lvl in order:
        rules = levels.get(lvl) or {}
        unmet: List[str] = []
        def chk(k: str, val: float, ge: float):
            if val < ge:
                unmet.append(f"{k}<{ge}")
        if "min_ilevel" in rules:
            chk("ilevel", vals.get("ilevel", 0.0), float(rules["min_ilevel"]))
        if "min_coverage" in rules:
            chk("coverage", vals.get("coverage", 0.0), float(rules["min_coverage"]))
        if "min_analyzed_ratio" in rules:
            chk("analyzed_ratio", vals.get("analyzed_ratio", 0.0), float(rules["min_analyzed_ratio"]))
        if "min_major_secondary_share" in rules:
            chk("major_secondary_share", vals.get("major_secondary_share", 0.0), float(rules["min_major_secondary_share"]))
        if "min_median_final_weight" in rules:
            chk("median_final_weight", vals.get("median_final_weight", 0.0), float(rules["min_median_final_weight"]))
        if "min_known_types" in rules:
            chk("known_types", vals.get("known_types", 0.0), float(rules["min_known_types"]))
        if "min_index_lines" in rules:
            if vals.get("index_lines", 0) < int(rules["min_index_lines"]):
                unmet.append(f"index_lines<{int(rules['min_index_lines'])}")
        if not unmet:
            return lvl, []
        if lvl == "RL0":
            return lvl, unmet
    return "RL0", ["no_rules_matched"]


def weighted_avg(items: List[dict], key_path: List[str], weight_key_path: List[str]) -> float:
    def get(obj, path, default=0.0):
        cur = obj
        for k in path:
            if not isinstance(cur, dict):
                return default
            cur = cur.get(k)
        try:
            return float(cur)
        except Exception:
            return default
    s = 0.0
    w = 0.0
    for it in items:
        val = get(it, key_path, 0.0)
        wt = get(it, weight_key_path, 0.0)
        s += val * wt
        w += wt
    return (s / w) if w else 0.0


def render(metrics: dict, policy: dict) -> str:
    g = metrics.get("global", {})
    docs = metrics.get("documents", [])
    # Global aggregates
    pages_total = int(g.get("pages_total") or 0) + int(g.get("frames_total") or 0)
    pages_done = int(g.get("pages_done") or 0) + int(g.get("frames_done") or 0)
    regions_total = int(g.get("regions_total") or 0)
    analyzed_regions = int(g.get("analyzed_regions") or 0)
    ilevel_glob = float(g.get("ilevel") or 0.0)
    index_lines = int(g.get("index_lines") or 0)
    coverage_glob = safe_ratio(pages_done, pages_total)

    # Approximate global quality/understanding from doc-level values weighted by regions_total
    ms_share_glob = weighted_avg(docs, ["quality", "share_major_secondary"], ["coverage", "regions_total"])
    med_final_glob = weighted_avg(docs, ["quality", "median_final_weight"], ["coverage", "regions_total"])
    known_types_glob = weighted_avg(docs, ["understanding", "known_types"], ["coverage", "regions_total"])

    lvl, unmet = evaluate_readiness(policy, {
        "ilevel": ilevel_glob,
        "coverage": coverage_glob,
        "analyzed_ratio": safe_ratio(analyzed_regions, regions_total),
        "major_secondary_share": ms_share_glob,
        "median_final_weight": med_final_glob,
        "known_types": known_types_glob,
        "index_lines": index_lines,
    })

    # CTA enable if RL2 or above
    can_push = lvl in {"RL2", "RL3"}
    cmd = "python3 scripts/qdrant_push.py --index out/openai_embeddings.ndjson --collection aipik_visual"

    # Sort documents by RL/I-level ascending
    def sort_key(d):
        order = {"RL0": 0, "RL1": 1, "RL2": 2, "RL3": 3}
        return (order.get(d.get("rl") or "RL0", 0), float(d.get("ilevel") or 0.0))
    docs2 = sorted(docs, key=sort_key)

    color = {"RL0": "#9ca3af", "RL1": "#f59e0b", "RL2": "#10b981", "RL3": "#059669"}.get(lvl, "#9ca3af")
    status_box = f"<div style='padding:10px 14px;border-left:6px solid {color};background:#f9fafb;border:1px solid #e5e7eb;border-radius:4px'><b>Global Readiness: {lvl}</b><br>Unmet: {html.escape(', '.join(unmet) or '—')}</div>"

    return (
        "<!doctype html><meta charset='utf-8'><title>Readiness</title>"
        "<meta http-equiv='refresh' content='20'>"
        "<style>body{font-family:system-ui,Arial,sans-serif;max-width:1040px;margin:24px auto;line-height:1.45}"
        ".grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}"
        ".card{border:1px solid #e5e7eb;border-radius:8px;padding:12px;background:#fff}"
        "table{border-collapse:collapse;width:100%;margin-top:10px} th,td{border:1px solid #e5e7eb;padding:6px 8px;font-size:14px;text-align:left} th{background:#f8fafc}"
        ".muted{color:#6b7280;font-size:12px} .btn{display:inline-block;padding:10px 16px;border-radius:6px;border:1px solid #c7d2fe;background:#eef2ff;color:#1e40af;font-weight:600;cursor:pointer}"
        ".btn.disabled{opacity:.65;cursor:not-allowed} code{background:#f3f4f6;padding:2px 6px;border-radius:4px}"
        "</style>"
        "<h1>Readiness & Qdrant Publish</h1>"
        f"{status_box}"
        "<div class='grid' style='margin-top:16px'>"
          "<div class='card'>"
            "<div class='muted'>Global</div>"
            f"<div>Coverage: <b>{pct(pages_done, pages_total):.1f}%</b> ({pages_done}/{pages_total})</div>"
            f"<div>Analysis: <b>{pct(analyzed_regions, regions_total):.1f}%</b> ({analyzed_regions}/{regions_total})</div>"
            f"<div>I‑Level: <b>{ilevel_glob:.2f}</b></div>"
            f"<div>Index lines: <b>{index_lines}</b></div>"
          "</div>"
          "<div class='card'>"
            "<div class='muted'>Action</div>"
            f"<div style='margin:6px 0'>Command: <code>{html.escape(cmd)}</code></div>"
            f"<button class='btn{' disabled' if not can_push else ''}' id='copy'>Copy push command</button>"
            f"<div class='muted' style='margin-top:6px'>{'Allowed (RL≥2). Review before publishing.' if can_push else 'Not recommended: gates not met (see unmet).'}</div>"
          "</div>"
        "</div>"
        "<h2>Documents</h2>"
        "<table>"
        "<tr><th>Title</th><th>I‑Level</th><th>RL</th><th>Unmet</th><th>Pages</th><th>Done</th><th>Coverage %</th></tr>"
        + "".join(
            f"<tr><td>{html.escape(d.get('title') or d.get('slug') or '')}</td>"
            f"<td>{(d.get('ilevel') or 0):.2f}</td>"
            f"<td>{html.escape(str(d.get('rl') or ''))}</td>"
            f"<td>{html.escape(','.join(d.get('unmet') or []))}</td>"
            f"<td>{int(d.get('coverage',{}).get('pages_total',0))}</td>"
            f"<td>{int(d.get('coverage',{}).get('pages_done',0))}</td>"
            f"<td>{pct(int(d.get('coverage',{}).get('pages_done',0)), int(d.get('coverage',{}).get('pages_total',0))):.1f}</td>"
            "</tr>"
            for d in docs2
          )
        + "</table>"
        "<p style='margin-top:16px'>Links: <a href='../index.html'>Portal Home</a> · <a href='../monitoring/index.html'>Monitoring</a></p>"
        "<script>(function(){var btn=document.getElementById('copy'); if(btn){btn.addEventListener('click',function(){navigator.clipboard&&navigator.clipboard.writeText('" + html.escape(cmd) + "').then(()=>{btn.textContent='Copied!'; setTimeout(()=>btn.textContent='Copy push command',1500);});});}})();</script>"
    )


def main():
    ap = argparse.ArgumentParser(description="Generate readiness page with RL and Qdrant CTA")
    ap.add_argument("--metrics", default="out/portal/metrics.json")
    ap.add_argument("--policy", default="config/readiness_policy.yaml")
    ap.add_argument("--out", default="out/portal/readiness/index.html")
    args = ap.parse_args()

    metrics = load_json(Path(args.metrics), default={})
    policy = load_readiness_policy(Path(args.policy))
    html_out = render(metrics, policy)
    outp = Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(html_out, encoding="utf-8")
    print(f"Wrote {outp}")


if __name__ == "__main__":
    main()

