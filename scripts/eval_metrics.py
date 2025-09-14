#!/usr/bin/env python3
import argparse
import json
import math
from pathlib import Path
from typing import List, Dict


def load_ndjson(path: Path):
    items = []
    with open(path, "r") as f:
        for line in f:
            if not line.strip():
                continue
            items.append(json.loads(line))
    return items


def dot(a: List[float], b: List[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def norm(a: List[float]) -> float:
    return math.sqrt(sum(x * x for x in a))


def cosine_sim(a: List[float], b: List[float]) -> float:
    na, nb = norm(a), norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return dot(a, b) / (na * nb)


def embed_openai_batch(texts: List[str], model: str) -> List[List[float]]:
    from openai import OpenAI

    client = OpenAI()
    resp = client.embeddings.create(model=model, input=texts)
    return [d.embedding for d in resp.data]


def ndcg_at_k(positives: set, ranked_ids: List[int], k: int) -> float:
    dcg = 0.0
    for i, pid in enumerate(ranked_ids[:k], start=1):
        rel = 1.0 if pid in positives else 0.0
        if rel:
            dcg += rel / math.log2(i + 1)
    ideal = 0.0
    for i in range(1, min(k, len(positives)) + 1):
        ideal += 1.0 / math.log2(i + 1)
    return dcg / ideal if ideal > 0 else 0.0


def main():
    p = argparse.ArgumentParser(description="Compute Recall@k, MRR, nDCG over annotated queries")
    p.add_argument("--index", default="out/openai_embeddings.ndjson")
    p.add_argument("--eval", default="eval/queries.jsonl")
    p.add_argument("--k", type=int, nargs="*", default=[1, 3, 5])
    p.add_argument("--model", default="text-embedding-3-large")
    args = p.parse_args()

    items = load_ndjson(Path(args.index))
    id_to_vec: Dict[int, List[float]] = {it["id"]: it["vector"] for it in items}

    eval_recs = []
    with open(args.eval, "r") as f:
        for line in f:
            if line.strip():
                eval_recs.append(json.loads(line))

    queries = [r["query"] for r in eval_recs]
    qvecs = embed_openai_batch(queries, model=args.model)

    totals = {f"recall@{k}": 0.0 for k in args.k}
    totals.update({f"ndcg@{k}": 0.0 for k in args.k})
    mrr_total = 0.0
    used = 0

    for rec, qv in zip(eval_recs, qvecs):
        positives = set(rec.get("positive_ids", []) or [])
        if not positives:
            continue
        # rank all by cosine
        scores = []
        for it in items:
            sim = cosine_sim(qv, it["vector"])  # type: ignore
            scores.append((sim, it["id"]))
        scores.sort(reverse=True)
        ranked_ids = [id for _, id in scores]

        # recall@k, ndcg@k
        for k in args.k:
            topk = set(ranked_ids[:k])
            hit = 1.0 if (positives & topk) else 0.0
            totals[f"recall@{k}"] += hit
            totals[f"ndcg@{k}"] += ndcg_at_k(positives, ranked_ids, k)

        # MRR
        rr = 0.0
        for idx, rid in enumerate(ranked_ids, start=1):
            if rid in positives:
                rr = 1.0 / idx
                break
        mrr_total += rr
        used += 1

    if used == 0:
        print("No queries with positive_ids found. Fill eval/queries.jsonl and rerun.")
        return

    for k in args.k:
        print(f"recall@{k}: {totals[f'recall@{k}'] / used:.3f}")
    for k in args.k:
        print(f"ndcg@{k}: {totals[f'ndcg@{k}'] / used:.3f}")
    print(f"MRR: {mrr_total / used:.3f} (over {used} annotated queries)")


if __name__ == "__main__":
    main()
