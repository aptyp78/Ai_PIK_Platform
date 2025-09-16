#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description="Prepare a TSV for manual labeling of positives")
    p.add_argument("--eval", default="eval/queries.jsonl")
    p.add_argument("--out", default="eval/labels.tsv")
    p.add_argument("--start", type=int, default=1, help="Start index (1-based, inclusive)")
    p.add_argument("--end", type=int, default=0, help="End index (1-based, inclusive; 0=all)")
    args = p.parse_args()

    rows = [json.loads(l) for l in Path(args.eval).read_text(encoding="utf-8").splitlines() if l.strip()]
    start = max(1, args.start)
    end = args.end if args.end > 0 else len(rows)

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("idx\tquery\tsuggested_ids\tpositive_ids\n")
        for i, rec in enumerate(rows, start=1):
            if i < start or i > end:
                continue
            sugg_ids = [str(it.get("id")) for it in (rec.get("suggested_topk") or [])]
            f.write(f"{i}\t{rec.get('query')}\t{','.join(sugg_ids)}\t\n")
    print(f"Wrote template: {args.out} (rows {start}..{end})")


if __name__ == "__main__":
    main()

