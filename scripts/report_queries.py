#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from typing import List, Dict, Tuple
import math


def load_ndjson(path: Path) -> List[Dict]:
    items = []
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


def embed_openai_batch(texts: List[str], model: str) -> List[List[float]]:
    from openai import OpenAI
    client = OpenAI()
    resp = client.embeddings.create(model=model, input=texts)
    return [d.embedding for d in resp.data]


def main():
    ap = argparse.ArgumentParser(description="Per-query retrieval report with flags for manual review")
    ap.add_argument("--index", default="out/openai_embeddings.ndjson")
    ap.add_argument("--eval", default="eval/queries.jsonl")
    ap.add_argument("--out-md", default="eval/review.md")
    ap.add_argument("--out-csv", default="eval/review.csv")
    ap.add_argument("--model", default="text-embedding-3-large")
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--sim-th", type=float, default=0.40)
    args = ap.parse_args()

    index = load_ndjson(Path(args.index))
    id2 = {it["id"]: it for it in index}
    eval_rows = [json.loads(l) for l in Path(args.eval).read_text().splitlines() if l.strip()]

    queries = [r["query"] for r in eval_rows]
    qvecs = embed_openai_batch(queries, model=args.model)

    flagged = []

    with open(args.out_md, "w") as md, open(args.out_csv, "w") as csv:
        csv.write("idx\tflag\ttop1_in_pos\ttop1_sim\ttop1_type\ttop1_id\tpositives\tquery\n")
        for i, (row, qv) in enumerate(zip(eval_rows, qvecs), start=1):
            scores: List[Tuple[float, Dict]] = []
            for it in index:
                sim = cosine(qv, it["vector"])  # type: ignore
                it2 = dict(it)
                it2["sim"] = float(sim)
                scores.append((sim, it2))
            scores.sort(key=lambda x: x[0], reverse=True)
            top = [it for _, it in scores[: args.k]]

            positives = set(row.get("positive_ids") or [])
            top1 = top[0]
            top1_in = top1["id"] in positives
            top1_sim = top1["sim"]
            top1_type = top1.get("meta", {}).get("type")
            need_flag = (not top1_in) or (top1_sim < args.sim_th) or (top1_type == "Image")

            flag_txt = "" if not need_flag else (
                "miss@1" if not top1_in else ("low_sim" if top1_sim < args.sim_th else "image_top1")
            )
            if need_flag:
                flagged.append((i, flag_txt, top1_sim))

            # write MD
            md.write(f"## Q{i}: {row['query']}\n")
            md.write(f"- positives: {sorted(positives)}\n")
            md.write(f"- top1: id={top1['id']} sim={top1_sim:.3f} type={top1_type}\n")
            md.write("- top candidates:\n")
            for j, it in enumerate(top, start=1):
                m = it.get("meta", {})
                preview = it.get("text", "").replace("\n", " ")[:300]
                md.write(f"  - #{j} id={it['id']} sim={it['sim']:.3f} type={m.get('type')} page={m.get('page')} file={m.get('filename')}\n")
                md.write(f"    {preview}\n")
            md.write("\n")

            # write CSV
            csv.write(
                f"{i}\t{flag_txt}\t{int(top1_in)}\t{top1_sim:.3f}\t{top1_type}\t{top1['id']}\t{sorted(positives)}\t{row['query']}\n"
            )

    # Summary
    print(f"Wrote {args.out_md} and {args.out_csv}")
    if flagged:
        flagged.sort(key=lambda x: x[2])
        print("Flagged queries (idx, reason, top1_sim):")
        for q in flagged[:10]:
            print(q)


if __name__ == "__main__":
    main()
