#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from typing import List, Dict, Any


PREFERRED_TYPES_DEFAULT = ["VisualFact", "VisualCaption"]
FALLBACK_TYPES_DEFAULT = ["Table", "NarrativeText", "Title", "Image", "Text"]


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def save_jsonl(path: Path, rows: List[Dict[str, Any]]):
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def choose_ids(suggested: List[Dict[str, Any]], max_ids: int,
               preferred_types: List[str], fallback_types: List[str]) -> List[int]:
    picked: List[int] = []
    def pick_from(types: List[str]):
        nonlocal picked
        for t in types:
            if len(picked) >= max_ids:
                return
            for s in suggested:
                sid = s.get("id")
                if sid in picked:
                    continue
                if s.get("type") == t:
                    picked.append(sid)
                    if len(picked) >= max_ids:
                        return
    pick_from(preferred_types)
    if len(picked) < max_ids:
        pick_from(fallback_types)
    # Final fallback: top by sim regardless of type
    if len(picked) < max_ids:
        for s in suggested:
            sid = s.get("id")
            if sid not in picked:
                picked.append(sid)
            if len(picked) >= max_ids:
                break
    return picked[:max_ids]


def main():
    ap = argparse.ArgumentParser(description="Auto-label eval/queries.jsonl positive_ids from suggested_topk")
    ap.add_argument("--infile", default="eval/queries.jsonl")
    ap.add_argument("--outfile", default="eval/queries.jsonl")
    ap.add_argument("--max", type=int, default=3)
    ap.add_argument("--force", action="store_true", help="Overwrite existing positive_ids")
    ap.add_argument("--preferred", default=",".join(PREFERRED_TYPES_DEFAULT), help="Comma-separated preferred types")
    ap.add_argument("--fallback", default=",".join(FALLBACK_TYPES_DEFAULT), help="Comma-separated fallback types")
    args = ap.parse_args()

    path = Path(args.infile)
    rows = load_jsonl(path)
    preferred = [t.strip() for t in args.preferred.split(",") if t.strip()]
    fallback = [t.strip() for t in args.fallback.split(",") if t.strip()]

    updated = 0
    for r in rows:
        pos = r.get("positive_ids")
        if (pos and isinstance(pos, list) and len(pos) > 0) and not args.force:
            continue
        sugg = r.get("suggested_topk") or []
        if not sugg:
            continue
        r["positive_ids"] = choose_ids(sugg, args.max, preferred, fallback)
        updated += 1

    outp = Path(args.outfile)
    # backup if overwriting
    if outp == path:
        bak = Path(str(outp) + ".bak")
        bak.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    save_jsonl(outp, rows)
    print(f"Auto-labeled {updated} queries → {outp}")


if __name__ == "__main__":
    main()
