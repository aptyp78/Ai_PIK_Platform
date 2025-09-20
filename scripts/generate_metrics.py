#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple


@dataclass
class Paths:
    portal_root: Path = Path("out/portal")
    regions_root: Path = Path("out/visual/regions/gdino_sam2")
    summaries_root: Path = Path("out/portal/summaries")
    index_path: Path = Path("out/openai_embeddings.ndjson")


def load_json(p: Path, default):
    try:
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def count_lines(p: Path) -> int:
    if not p.exists():
        return 0
    try:
        with p.open("r", encoding="utf-8", errors="ignore") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


def overlays_count_for_slug(regions_root: Path, slug: str) -> int:
    base = regions_root / slug
    if not base.exists():
        return 0
    return sum(1 for _ in base.glob("*/overlay.png") if _.exists())


def analyzed_regions_for_slug(regions_root: Path, slug: str) -> int:
    base = regions_root / slug
    if not base.exists():
        return 0
    # Count per-region struct.json as proxy for analysis
    return sum(1 for _ in base.rglob("regions/region-*.struct.json"))


def regions_total_for_slug(regions_root: Path, slug: str) -> int:
    base = regions_root / slug
    if not base.exists():
        return 0
    tot = 0
    for p in base.glob("*/regions.json"):
        try:
            js = json.loads(p.read_text(encoding="utf-8"))
            c = int(js.get("count") or len(js.get("regions") or []))
            tot += c
        except Exception:
            pass
    return tot


def safe_ratio(a: int, b: int) -> float:
    return float(a) / float(b) if b > 0 else 0.0


def build_metrics(paths: Paths) -> dict:
    coverage = load_json(paths.portal_root / "coverage.json", default={})
    portal_idx = load_json(paths.portal_root / "portal_index.json", default={"playbooks": [], "framesets": []})
    playbooks = portal_idx.get("playbooks") or []

    docs_out: List[dict] = []
    g_pages_total = 0
    g_pages_done = 0
    g_frames_total = 0
    g_frames_done = 0
    g_regions_total = 0
    g_analyzed = 0

    # Build fast lookup for coverage by slug
    cov_by_slug: Dict[str, dict] = coverage if isinstance(coverage, dict) else {}

    for d in playbooks:
        slug = d.get("slug")
        if not slug:
            continue
        cov = cov_by_slug.get(slug, {})
        pages_total = int(cov.get("pages_total") or 0)
        pages_done = int(cov.get("pages_done") or 0)
        frames_total = int(cov.get("frames_total") or 0)
        frames_done = int(cov.get("frames_done") or 0)
        regions_total = int(cov.get("regions_total") or 0)
        overlays = overlays_count_for_slug(paths.regions_root, slug)
        analyzed = analyzed_regions_for_slug(paths.regions_root, slug)

        g_pages_total += pages_total
        g_pages_done += pages_done
        g_frames_total += frames_total
        g_frames_done += frames_done
        g_regions_total += regions_total
        g_analyzed += analyzed

        # Phase 1 heuristic I-Level: use coverage ratio only
        cov_ratio = max(
            safe_ratio(pages_done, pages_total),
            safe_ratio(frames_done, frames_total),
        )
        doc = {
            "slug": slug,
            "title": d.get("title") or slug,
            "coverage": {
                "pages_total": pages_total,
                "pages_done": pages_done,
                "frames_total": frames_total,
                "frames_done": frames_done,
                "regions_total": regions_total,
                "overlays": overlays,
            },
            "quality": {},
            "understanding": {},
            "ilevel": round(cov_ratio, 4),
        }
        docs_out.append(doc)

    # Global KPIs
    index_lines = count_lines(paths.index_path)
    cov_ratio_global = safe_ratio(g_pages_done + g_frames_done, g_pages_total + g_frames_total)
    metrics = {
        "generated_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "global": {
            "docs": len(docs_out),
            "pages_total": g_pages_total,
            "pages_done": g_pages_done,
            "frames_total": g_frames_total,
            "frames_done": g_frames_done,
            "regions_total": g_regions_total,
            "analyzed_regions": g_analyzed,
            "index_lines": index_lines,
            "ilevel": round(cov_ratio_global, 4),
        },
        "documents": docs_out,
    }
    return metrics


def write_json(p: Path, obj: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Generate metrics.json for monitoring portal (Phase 1: coverage-driven)")
    ap.add_argument("--out", default="out/portal/metrics.json")
    ap.add_argument("--regions-root", default="out/visual/regions/gdino_sam2")
    ap.add_argument("--index", default="out/openai_embeddings.ndjson")
    args = ap.parse_args()

    paths = Paths(
        portal_root=Path("out/portal"),
        regions_root=Path(args.regions_root),
        summaries_root=Path("out/portal/summaries"),
        index_path=Path(args.index),
    )
    metrics = build_metrics(paths)
    write_json(Path(args.out), metrics)
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()

