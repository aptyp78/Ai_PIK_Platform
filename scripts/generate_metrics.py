#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Dict, List, Tuple, Any


@dataclass
class Paths:
    portal_root: Path = Path("out/portal")
    regions_root: Path = Path("out/visual/regions/gdino_sam2")
    summaries_root: Path = Path("out/portal/summaries")
    index_path: Path = Path("out/openai_embeddings.ndjson")
    readiness_policy: Path = Path("config/readiness_policy.yaml")


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

    policy = load_readiness_policy(paths.readiness_policy)

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

        doc_metrics = compute_doc_metrics(paths, slug, d.get("title") or slug, cov, policy)
        docs_out.append(doc_metrics)

        g_pages_total += int(doc_metrics["coverage"]["pages_total"]) or 0
        g_pages_done += int(doc_metrics["coverage"]["pages_done"]) or 0
        g_frames_total += int(doc_metrics["coverage"]["frames_total"]) or 0
        g_frames_done += int(doc_metrics["coverage"]["frames_done"]) or 0
        g_regions_total += int(doc_metrics["coverage"]["regions_total"]) or 0
        g_analyzed += int(doc_metrics.get("analyzed_regions") or 0)

    # Global KPIs
    index_lines = count_lines(paths.index_path)
    cov_ratio_global = safe_ratio(g_pages_done + g_frames_done, g_pages_total + g_frames_total)
    # Aggregate I-level as coverage-weighted mean of doc ilevels
    wsum = 0.0
    w = 0.0
    for doc in docs_out:
        pt = int(doc["coverage"]["pages_total"]) + int(doc["coverage"]["frames_total"]) or 1
        wsum += (doc.get("ilevel") or 0.0) * pt
        w += pt
    global_ilevel = round((wsum / w) if w else cov_ratio_global, 4)

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
            "ilevel": global_ilevel,
        },
        "documents": docs_out,
    }
    return metrics


def load_readiness_policy(path: Path) -> dict:
    # Try to use PyYAML if available, otherwise fallback to defaults
    default = {
        "levels": {
            "RL0": {"min_ilevel": 0.0, "min_coverage": 0.0},
            "RL1": {"min_ilevel": 0.50, "min_coverage": 0.50, "min_analyzed_ratio": 0.60, "min_major_secondary_share": 0.25, "min_index_lines": 500},
            "RL2": {"min_ilevel": 0.70, "min_coverage": 0.70, "min_analyzed_ratio": 0.80, "min_median_final_weight": 0.60, "min_known_types": 0.70, "min_index_lines": 2000},
            "RL3": {"min_ilevel": 0.85, "min_coverage": 0.95},
        },
        "weights": {"ilevel": {"coverage": 0.4, "quality": 0.4, "understanding": 0.2}},
        "quality_norm": {"auto_score": {"min": 0.0, "max": 1.0}, "final_weight": {"min": 0.0, "max": 1.0}, "confidence_visual": {"min": 0.0, "max": 1.0}},
    }
    try:
        import yaml  # type: ignore
        if path.exists():
            return yaml.safe_load(path.read_text(encoding="utf-8")) or default
    except Exception:
        pass
    return default


def clamp01(x: float) -> float:
    return 0.0 if x is None else 1.0 if x > 1.0 else 0.0 if x < 0.0 else float(x)


def norm(val_list: List[float], vmin: float, vmax: float) -> float:
    vals = [v for v in val_list if isinstance(v, (int, float))]
    if not vals:
        return 0.0
    m = median(vals)
    if vmax <= vmin:
        return clamp01(m)
    return clamp01((m - vmin) / (vmax - vmin))


def compute_doc_metrics(paths: Paths, slug: str, title: str, cov: Dict[str, Any], policy: Dict[str, Any]) -> dict:
    pages_total = int(cov.get("pages_total") or 0)
    pages_done = int(cov.get("pages_done") or 0)
    frames_total = int(cov.get("frames_total") or 0)
    frames_done = int(cov.get("frames_done") or 0)
    regions_total = int(cov.get("regions_total") or 0)

    overlays = overlays_count_for_slug(paths.regions_root, slug)
    analyzed = analyzed_regions_for_slug(paths.regions_root, slug)

    # Per-region stats
    auto_scores: List[float] = []
    final_weights: List[float] = []
    confidences: List[float] = []
    tiers: List[str] = []
    known_type_cnt = 0
    total_regions = 0
    facts_cnt = 0

    # Per-item understanding: summaries/captions coverage
    items = sorted([p.name for p in (paths.regions_root / slug).glob("*") if p.is_dir()])
    sum_ru_ok = 0
    sum_en_ok = 0
    sum_total = 0
    cap_ru_have = 0
    cap_total = 0

    for item_id in items:
        item_dir = paths.regions_root / slug / item_id
        agg = item_dir / "regions.json"
        regs: List[Dict[str, Any]] = []
        if agg.exists():
            try:
                js = json.loads(agg.read_text(encoding="utf-8"))
                regs = js.get("regions") or []
            except Exception:
                regs = []
        # Summaries coverage
        sfile = paths.summaries_root / slug / f"{item_id}.json"
        if sfile.exists():
            try:
                sjs = json.loads(sfile.read_text(encoding="utf-8"))
                if (sjs.get("summary_ru") or "").strip():
                    sum_ru_ok += 1
                if (sjs.get("summary_en") or "").strip():
                    sum_en_ok += 1
            except Exception:
                pass
        sum_total += 1
        # Captions coverage (translated)
        cmap_file = paths.summaries_root / slug / f"{item_id}.captions.json"
        cap_map = {}
        if cmap_file.exists():
            try:
                cap_map = json.loads(cmap_file.read_text(encoding="utf-8"))
            except Exception:
                cap_map = {}
        # Iterate regions
        for r in regs:
            total_regions += 1
            # known types
            rtype = (r.get("struct_type") or "").strip()
            if not rtype:
                # try to read struct.json
                rid = r.get("rid")
                if rid is not None:
                    sj = item_dir / "regions" / f"region-{rid}.struct.json"
                    if sj.exists():
                        try:
                            o = json.loads(sj.read_text(encoding="utf-8"))
                            rtype = (o.get("artifact_type") or "").strip()
                            # Scores/tier if available
                            tg = o.get("Tagging") or {}
                            if isinstance(tg, dict):
                                a = tg.get("AutoScore")
                                if isinstance(a, (int, float)):
                                    auto_scores.append(float(a))
                                t = (tg.get("AutoTier") or "").strip()
                                if t:
                                    tiers.append(t)
                            sc = o.get("Scoring") or {}
                            if isinstance(sc, dict):
                                fw = sc.get("final_weight")
                                if isinstance(fw, (int, float)):
                                    final_weights.append(float(fw))
                                cf = sc.get("confidence_visual")
                                if isinstance(cf, (int, float)):
                                    confidences.append(float(cf))
                        except Exception:
                            pass
            else:
                known_type_cnt += 1
            # Facts
            fp = r.get("facts_path")
            if fp:
                try:
                    if (item_dir / fp).exists():
                        facts_cnt += 1
                except Exception:
                    pass
            # Captions RU
            rid = r.get("rid")
            if cap_map and rid is not None:
                cap_total += 1
                entry = cap_map.get(str(rid)) or {}
                if (entry.get("caption_ru") or "").strip():
                    cap_ru_have += 1

    # Derived metrics
    major_secondary_share = 0.0
    if tiers:
        ms = sum(1 for t in tiers if t.lower() in {"major", "secondary"})
        major_secondary_share = safe_ratio(ms, len(tiers))
    median_auto = median(auto_scores) if auto_scores else 0.0
    median_final = median(final_weights) if final_weights else 0.0
    mean_conf = (sum(confidences) / len(confidences)) if confidences else 0.0
    known_types_ratio = safe_ratio(known_type_cnt, total_regions)
    captions_ru_ratio = safe_ratio(cap_ru_have, cap_total)
    summary_ru_ratio = safe_ratio(sum_ru_ok, sum_total) if sum_total else 0.0
    summary_en_ratio = safe_ratio(sum_en_ok, sum_total) if sum_total else 0.0
    visual_facts_ratio = safe_ratio(facts_cnt, total_regions)

    # Normalize quality components using policy
    qn = (policy.get("quality_norm") or {})
    q_auto = norm([median_auto], (qn.get("auto_score") or {}).get("min", 0.0), (qn.get("auto_score") or {}).get("max", 1.0))
    q_final = norm([median_final], (qn.get("final_weight") or {}).get("min", 0.0), (qn.get("final_weight") or {}).get("max", 1.0))
    q_conf = norm([mean_conf], (qn.get("confidence_visual") or {}).get("min", 0.0), (qn.get("confidence_visual") or {}).get("max", 1.0))
    quality = sum([q_auto, major_secondary_share, q_final, q_conf]) / 4.0

    understanding = sum([
        known_types_ratio,
        summary_ru_ratio,
        summary_en_ratio,
        captions_ru_ratio,
        visual_facts_ratio,
    ]) / 5.0

    # Coverage component
    cov_ratio = max(
        safe_ratio(pages_done, pages_total),
        safe_ratio(frames_done, frames_total),
    )

    # I-Level
    w = (policy.get("weights") or {}).get("ilevel", {"coverage": 0.4, "quality": 0.4, "understanding": 0.2})
    ilevel = (
        (w.get("coverage", 0.4) * cov_ratio)
        + (w.get("quality", 0.4) * quality)
        + (w.get("understanding", 0.2) * understanding)
    )

    rl, unmet = evaluate_readiness(policy, {
        "ilevel": ilevel,
        "coverage": cov_ratio,
        "analyzed_ratio": safe_ratio(analyzed, total_regions) if total_regions else 0.0,
        "major_secondary_share": major_secondary_share,
        "median_final_weight": median_final,
        "known_types": known_types_ratio,
        "index_lines": count_lines(paths.index_path),
    })

    return {
        "slug": slug,
        "title": title,
        "coverage": {
            "pages_total": pages_total,
            "pages_done": pages_done,
            "frames_total": frames_total,
            "frames_done": frames_done,
            "regions_total": regions_total,
            "overlays": overlays,
        },
        "analyzed_regions": analyzed,
        "quality": {
            "median_auto_score": round(median_auto, 4),
            "share_major_secondary": round(major_secondary_share, 4),
            "median_final_weight": round(median_final, 4),
            "mean_confidence": round(mean_conf, 4),
        },
        "understanding": {
            "known_types": round(known_types_ratio, 4),
            "summary_ru": round(summary_ru_ratio, 4),
            "summary_en": round(summary_en_ratio, 4),
            "captions_ru": round(captions_ru_ratio, 4),
            "visual_facts": round(visual_facts_ratio, 4),
        },
        "ilevel": round(ilevel, 4),
        "rl": rl,
        "unmet": unmet,
    }


def evaluate_readiness(policy: Dict[str, Any], vals: Dict[str, float]) -> Tuple[str, List[str]]:
    levels = (policy.get("levels") or {})
    # Evaluate from highest to lowest
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
        # If RL0 has unmet, still return RL0 with unmet list
        if lvl == "RL0":
            return lvl, unmet
        # Otherwise continue to lower level
    return "RL0", ["no_rules_matched"]


def write_json(p: Path, obj: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Generate metrics.json for monitoring portal (Phase 2+: quality & readiness)")
    ap.add_argument("--out", default="out/portal/metrics.json")
    ap.add_argument("--regions-root", default="out/visual/regions/gdino_sam2")
    ap.add_argument("--index", default="out/openai_embeddings.ndjson")
    ap.add_argument("--log-jsonl", default="Logs/metrics.jsonl", help="Append snapshot to JSONL for trends")
    ap.add_argument("--no-log", action="store_true", help="Do not append JSONL snapshot")
    args = ap.parse_args()

    paths = Paths(
        portal_root=Path("out/portal"),
        regions_root=Path(args.regions_root),
        summaries_root=Path("out/portal/summaries"),
        index_path=Path(args.index),
    )
    metrics = build_metrics(paths)
    outp = Path(args.out)
    write_json(outp, metrics)
    print(f"Wrote {outp}")
    # Append snapshot to JSONL for trends
    if not args.no_log and args.log_jsonl:
        try:
            lj = Path(args.log_jsonl)
            lj.parent.mkdir(parents=True, exist_ok=True)
            # Keep only compact subset for trends (generated_at + global + per-doc ilevel)
            subset = {
                "generated_at": metrics.get("generated_at"),
                "global": metrics.get("global", {}),
                "documents": [
                    {"slug": d.get("slug"), "ilevel": d.get("ilevel"), "regions_total": d.get("coverage", {}).get("regions_total", 0)}
                    for d in (metrics.get("documents") or [])
                ],
            }
            with lj.open("a", encoding="utf-8") as f:
                f.write(json.dumps(subset, ensure_ascii=False) + "\n")
        except Exception:
            pass


if __name__ == "__main__":
    main()
