#!/usr/bin/env python3
import argparse
import json
import math
from pathlib import Path
from typing import Dict, List, Tuple


def load_ndjson(path: Path) -> List[Dict]:
    items: List[Dict] = []
    with open(path, "r") as f:
        for line in f:
            if line.strip():
                items.append(json.loads(line))
    return items


def dot(a: List[float], b: List[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def norm(a: List[float]) -> float:
    return math.sqrt(sum(x * x for x in a))


def cosine(a: List[float], b: List[float]) -> float:
    na, nb = norm(a), norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return dot(a, b) / (na * nb)


def embed_openai(texts: List[str], model: str) -> List[List[float]]:
    from openai import OpenAI

    client = OpenAI()
    resp = client.embeddings.create(model=model, input=texts)
    return [d.embedding for d in resp.data]


def main() -> None:
    ap = argparse.ArgumentParser(description="Augment eval/queries.jsonl with visual positives based on current index")
    ap.add_argument("--index", default="out/openai_embeddings.ndjson")
    ap.add_argument("--eval-in", default="eval/queries.jsonl")
    ap.add_argument("--eval-out", default="eval/queries.jsonl")
    ap.add_argument("--model", default="text-embedding-3-large")
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--sim-th", type=float, default=0.36, help="Similarity threshold for adding candidates")
    ap.add_argument("--max-add", type=int, default=2, help="Max candidate ids to add per query")
    ap.add_argument("--include-image", action="store_true", help="Also allow adding Image type as positive")
    ap.add_argument("--force-top1-if-miss", action="store_true", help="If top1 not in positives, add it when above --top1-th")
    ap.add_argument("--top1-th", type=float, default=0.28, help="Min sim for forced top1 add when missing")
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    index = load_ndjson(Path(args.index))
    eval_rows = [json.loads(l) for l in Path(args.eval_in).read_text().splitlines() if l.strip()]

    id2 = {it["id"]: it for it in index}

    queries = [r["query"] for r in eval_rows]
    qvecs = embed_openai(queries, model=args.model)

    updated = 0
    for rec, qv in zip(eval_rows, qvecs):
        scores: List[Tuple[float, Dict]] = []
        for it in index:
            sim = cosine(qv, it["vector"])  # type: ignore
            it2 = dict(it)
            it2["sim"] = float(sim)
            scores.append((sim, it2))
        scores.sort(key=lambda x: x[0], reverse=True)
        top = [it for _, it in scores[: args.k]]

        allowed_types = {"VisualCaption", "VisualFact"}
        if args.include_image:
            allowed_types.add("Image")
        visual = [it for it in top if it.get("meta", {}).get("type") in allowed_types]
        visual = [it for it in visual if it.get("sim", 0.0) >= args.sim_th]
        if not visual:
            # If nothing passed threshold but top1 seems clearly relevant, optionally add it
            if args.force_top1_if_miss and top:
                t1 = top[0]
                if t1.get("sim", 0.0) >= args.top1_th and t1.get("meta", {}).get("type") in allowed_types:
                    visual = [t1]
                else:
                    continue
        pos = set(rec.get("positive_ids", []) or [])
        added = 0
        for it in visual:
            vid = int(it["id"])
            if vid not in pos:
                pos.add(vid)
                added += 1
            if added >= args.max_add:
                break
        if added:
            rec["positive_ids"] = sorted(pos)
            updated += 1

    if args.dry:
        print(f"Would update {updated} queries (dry run)")
        return

    # Backup original
    src = Path(args.eval_in)
    if args.eval_out == args.eval_in:
        bak = src.with_suffix(src.suffix + ".bak")
        bak.write_text(src.read_text())
    # Write updated
    with open(args.eval_out, "w") as f:
        for r in eval_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"Updated positives for {updated} queries -> {args.eval_out}")


if __name__ == "__main__":
    main()
