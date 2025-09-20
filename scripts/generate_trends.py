#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List, Dict, Any


def tail_jsonl(path: Path, max_lines: int = 300) -> List[dict]:
    if not path.exists():
        return []
    # Read all then keep last N (file is expected to be small-ish)
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        arr: List[dict] = []
        for line in lines[-max_lines:]:
            line = line.strip()
            if not line:
                continue
            try:
                arr.append(json.loads(line))
            except Exception:
                continue
        return arr
    except Exception:
        return []


def compute_trends(snapshots: List[dict]) -> dict:
    times: List[str] = []
    ilevel: List[float] = []
    coverage: List[float] = []
    analysis: List[float] = []
    index_lines: List[int] = []
    alerts: List[str] = []

    def ratio(a: float, b: float) -> float:
        return (a / b) if b else 0.0

    for s in snapshots:
        times.append(s.get("generated_at"))
        g = s.get("global", {})
        ilevel.append(float(g.get("ilevel") or 0.0))
        pages_total = (g.get("pages_total") or 0) + (g.get("frames_total") or 0)
        pages_done = (g.get("pages_done") or 0) + (g.get("frames_done") or 0)
        coverage.append(ratio(float(pages_done), float(pages_total)))
        analysis.append(ratio(float(g.get("analyzed_regions") or 0), float(g.get("regions_total") or 0)))
        index_lines.append(int(g.get("index_lines") or 0))

    # Alerts heuristics
    if len(ilevel) >= 2 and ilevel[-1] < ilevel[-2] - 0.05:
        alerts.append("I‑Level dropped >5% since last snapshot")
    if len(analysis) >= 3 and abs(analysis[-1] - analysis[-2]) < 1e-6 and abs(analysis[-2] - analysis[-3]) < 1e-6:
        alerts.append("Analysis stalled (no progress in 3 snapshots)")
    if len(index_lines) >= 2 and index_lines[-1] < index_lines[-2]:
        alerts.append("Index lines decreased — check index rebuild logic")

    return {
        "time": times,
        "ilevel": ilevel,
        "coverage": coverage,
        "analysis": analysis,
        "index_lines": index_lines,
        "alerts": alerts,
        "count": len(times),
    }


def main():
    ap = argparse.ArgumentParser(description="Compute trends from Logs/metrics.jsonl and write portal metrics_trends.json")
    ap.add_argument("--jsonl", default="Logs/metrics.jsonl")
    ap.add_argument("--out", default="out/portal/metrics_trends.json")
    ap.add_argument("--max", type=int, default=300)
    args = ap.parse_args()

    snaps = tail_jsonl(Path(args.jsonl), max_lines=args.max)
    trends = compute_trends(snaps)
    outp = Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(trends, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {outp} (points={trends.get('count')})")


if __name__ == "__main__":
    main()

