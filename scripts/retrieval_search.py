#!/usr/bin/env python3
import argparse
import json
import math
from pathlib import Path
from typing import List, Tuple


def load_ndjson(path: Path):
    items = []
    with open(path, "r") as f:
        for line in f:
            if not line.strip():
                continue
            obj = json.loads(line)
            items.append(obj)
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


def embed_query_openai(text: str, model: str = "text-embedding-3-large") -> List[float]:
    from openai import OpenAI  # requires env OPENAI_API_KEY

    client = OpenAI()
    resp = client.embeddings.create(model=model, input=[text])
    return resp.data[0].embedding


def main():
    p = argparse.ArgumentParser(description="Cosine search over precomputed OpenAI embeddings (NDJSON)")
    p.add_argument("--index", default="out/openai_embeddings.ndjson", help="Path to NDJSON with vectors")
    p.add_argument("--query", required=True, help="Search query (any language)")
    p.add_argument("--k", type=int, default=5, help="Top K results")
    p.add_argument("--model", default="text-embedding-3-large", help="OpenAI embedding model for the query")
    args = p.parse_args()

    items = load_ndjson(Path(args.index))
    qvec = embed_query_openai(args.query, model=args.model)

    scored: List[Tuple[float, dict]] = []
    for it in items:
        sim = cosine_sim(qvec, it["vector"])  # type: ignore
        scored.append((sim, it))
    scored.sort(key=lambda x: x[0], reverse=True)

    for rank, (sim, it) in enumerate(scored[: args.k], start=1):
        meta = it.get("meta", {})
        text = it.get("text", "")
        preview = text.replace("\n", " ")[:200]
        print(f"#{rank} sim={sim:.3f} page={meta.get('page')} type={meta.get('type')} span={meta.get('span')} id={it.get('id')}")
        print(f"   file={meta.get('filename')}")
        print(f"   {preview}…\n")


if __name__ == "__main__":
    main()
