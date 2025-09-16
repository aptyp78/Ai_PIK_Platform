#!/usr/bin/env python3
import argparse
import json
import math
import os
from pathlib import Path
from typing import List, Dict, Tuple


def load_ndjson(path: Path):
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
    ap = argparse.ArgumentParser(description="Refresh suggested_topk for queries.jsonl against current index")
    ap.add_argument("--index", default="out/openai_embeddings.ndjson")
    ap.add_argument("--eval", default="eval/queries.jsonl")
    ap.add_argument("--out", default="eval/queries.jsonl")
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--model", default="text-embedding-3-large")
    ap.add_argument("--prefer-visual", action="store_true")
    ap.add_argument("--type-weights", default=None)
    args = ap.parse_args()

    items = load_ndjson(Path(args.index))
    # type weights
    type_weights = {"Text": 1.0, "VisualCaption": 1.0, "VisualFact": 1.0, "Image": 0.95, "Table": 1.0}
    if args.prefer_visual:
        type_weights.update({"VisualCaption": 1.1, "VisualFact": 1.05})
    if args.type_weights:
        for tok in args.type_weights.split(','):
            if not tok.strip():
                continue
            if '=' in tok:
                k, v = tok.split('=', 1)
                try:
                    type_weights[k.strip()] = float(v)
                except Exception:
                    pass
    # tag weights
    tag_weights_env = os.environ.get('TAG_WEIGHTS')
    tag_weights = {"Canvas": 1.06, "Assessment": 1.05, "Diagram": 1.04, "Pillar": 1.06, "Layer": 1.05}
    if tag_weights_env:
        for tok in tag_weights_env.split(','):
            if '=' in tok:
                k, v = tok.split('=', 1)
                try:
                    tag_weights[k.strip()] = float(v)
                except Exception:
                    pass

    recs = []
    with open(args.eval, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                recs.append(json.loads(line))
    queries = [r['query'] for r in recs]
    qvecs = embed_openai_batch(queries, model=args.model)

    for rec, qv in zip(recs, qvecs):
        scored: List[Tuple[float, Dict]] = []
        for it in items:
            sim = cosine_sim(qv, it['vector'])  # type: ignore
            m = it.get('meta', {})
            t = m.get('type')
            tw = type_weights.get(t, 1.0)
            tagw = 1.0
            tags = m.get('tags') or []
            if isinstance(tags, list) and tags:
                for tg in tags:
                    tagw = max(tagw, tag_weights.get(tg, 1.0))
            s = sim * tw * tagw
            scored.append((s, it))
        scored.sort(key=lambda x: x[0], reverse=True)
        top = []
        for s, it in scored[: args.k]:
            m = it.get('meta', {})
            top.append({
                'id': it.get('id'),
                'sim': s,
                'page': m.get('page'),
                'type': m.get('type'),
                'span': m.get('span'),
                'filename': m.get('filename'),
            })
        rec['suggested_topk'] = top

    with open(args.out, 'w', encoding='utf-8') as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    print(f"Updated suggested_topk for {len(recs)} queries -> {args.out}")


if __name__ == '__main__':
    main()

