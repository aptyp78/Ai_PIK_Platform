#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Any, List


def ensure_dir(p: Path):
    p.parent.mkdir(parents=True, exist_ok=True)


def build_summary(regs: List[Dict[str, Any]]) -> Dict[str, Any]:
    types: Dict[str, int] = {}
    caps: List[str] = []
    for r in regs:
        t = (r.get("struct_type") or r.get("type") or "").strip()
        if t:
            types[t] = types.get(t, 0) + 1
        c = (r.get("caption") or "").strip()
        if c:
            caps.append(c)
    top = ", ".join([k for k, _ in sorted(types.items(), key=lambda kv: kv[1], reverse=True)[:3]])
    lead = caps[0] if caps else ""
    if lead and len(lead) > 220:
        lead = lead[:220] + "…"
    sr = "; ".join([p for p in [top, lead] if p]) or "Сводка недоступна"
    se = sr  # simple fallback
    return {
        "summary_ru": sr,
        "summary_en": se,
        "bullets": [f"Типы: {top}"] if top else [],
        "bullets_en": [f"Types: {top}"] if top else [],
        "regions": len(regs),
        "source": "heuristic",
    }


def main():
    ap = argparse.ArgumentParser(description="Backfill summaries and captions (RU/EN heuristic fallback) for unified regions")
    ap.add_argument("--root", default="out/visual/regions/gdino_sam2")
    ap.add_argument("--out-root", default="out/portal/summaries")
    args = ap.parse_args()

    root = Path(args.root)
    out_root = Path(args.out_root)
    for slug_dir in sorted([p for p in root.iterdir() if p.is_dir()], key=lambda p: p.name):
        for item_dir in sorted([p for p in slug_dir.iterdir() if p.is_dir()]):
            agg = item_dir / "regions.json"
            if not agg.exists():
                continue
            try:
                js = json.loads(agg.read_text(encoding="utf-8"))
                regs = js.get("regions") or []
            except Exception:
                regs = []
            # summary
            out_json = out_root / slug_dir.name / f"{item_dir.name}.json"
            if not out_json.exists():
                ensure_dir(out_json)
                out_json.write_text(json.dumps(build_summary(regs), ensure_ascii=False, indent=2), encoding="utf-8")
            # captions map
            cap_out = out_root / slug_dir.name / f"{item_dir.name}.captions.json"
            if not cap_out.exists():
                m: Dict[str, Dict[str, str]] = {}
                for r in regs:
                    rid = r.get("rid")
                    if rid is None:
                        continue
                    c = (r.get("caption") or "").strip()
                    m[str(rid)] = {"caption_en": c, "caption_ru": c}
                ensure_dir(cap_out)
                cap_out.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Backfill completed.")


if __name__ == "__main__":
    main()

