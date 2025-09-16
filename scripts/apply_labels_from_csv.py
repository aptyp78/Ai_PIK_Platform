#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def parse_pos_ids(val: str):
    val = (val or "").strip()
    if not val:
        return []
    # Accept JSON-like [1,2] or comma-separated "1,2,3"
    if val.startswith("["):
        try:
            arr = json.loads(val)
            return [int(x) for x in arr]
        except Exception:
            pass
    toks = [t.strip() for t in val.split(",") if t.strip()]
    out = []
    for t in toks:
        try:
            out.append(int(t))
        except Exception:
            pass
    return out


def main():
    p = argparse.ArgumentParser(description="Apply manual labels (positive_ids) from TSV to queries.jsonl")
    p.add_argument("--eval", default="eval/queries.jsonl")
    p.add_argument("--labels", default="eval/labels.tsv")
    p.add_argument("--out", default="eval/queries.jsonl")
    args = p.parse_args()

    rows = [json.loads(l) for l in Path(args.eval).read_text(encoding="utf-8").splitlines() if l.strip()]
    updates = {}
    with open(args.labels, "r", encoding="utf-8") as f:
        header = f.readline()
        for line in f:
            if not line.strip():
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 4:
                continue
            try:
                idx = int(parts[0])
            except Exception:
                continue
            pos = parse_pos_ids(parts[3])
            updates[idx] = pos

    for i, rec in enumerate(rows, start=1):
        if i in updates:
            rec["positive_ids"] = updates[i]

    with open(args.out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"Applied labels for {len(updates)} queries -> {args.out}")


if __name__ == "__main__":
    main()

