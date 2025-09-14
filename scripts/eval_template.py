#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from typing import List, Dict
import math


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


def main():
    p = argparse.ArgumentParser(description="Generate eval JSONL template with suggested top-k for each query")
    p.add_argument("--index", default="out/openai_embeddings.ndjson", help="Path to NDJSON index")
    p.add_argument("--queries", default="eval/queries.txt", help="Path to queries .txt (one per line)")
    p.add_argument("--out", default="eval/queries.jsonl", help="Output JSONL with suggested ids and empty positives")
    p.add_argument("--k", type=int, default=5)
    p.add_argument("--model", default="text-embedding-3-large")
    args = p.parse_args()

    items = load_ndjson(Path(args.index))
    with open(args.queries, "r") as f:
        queries = [q.strip() for q in f if q.strip()]

    qvecs = embed_openai_batch(queries, model=args.model)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as w:
        for q, qv in zip(queries, qvecs):
            scored = []
            for it in items:
                sim = cosine_sim(qv, it["vector"])  # type: ignore
                meta = it.get("meta", {})
                text = it.get("text", "")
                preview = text.replace("\n", " ")[:200]
                scored.append({
                    "id": it.get("id"),
                    "sim": sim,
                    "page": meta.get("page"),
                    "type": meta.get("type"),
                    "span": meta.get("span"),
                    "filename": meta.get("filename"),
                    "preview": preview,
                })
            scored.sort(key=lambda x: x["sim"], reverse=True)
            rec = {
                "query": q,
                "suggested_topk": scored[: args.k],
                "positive_ids": [],
            }
            w.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"Wrote template -> {out}")


if __name__ == "__main__":
    main()
