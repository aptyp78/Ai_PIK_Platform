#!/usr/bin/env python3
import argparse
import json
import math
from pathlib import Path
from typing import List


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


def embed_query_openai(text: str, model: str = "text-embedding-3-large") -> List[float]:
    from openai import OpenAI

    client = OpenAI()
    resp = client.embeddings.create(model=model, input=[text])
    return resp.data[0].embedding


def answer_with_openai(query: str, contexts: List[dict], chat_model: str = "gpt-4o-mini") -> str:
    from openai import OpenAI

    client = OpenAI()
    # Build context block
    ctx_parts = []
    for i, c in enumerate(contexts, start=1):
        meta = c.get("meta", {})
        header = (
            f"[CTX {i}] type={meta.get('type')} file={meta.get('filename')} page={meta.get('page')}"
            f" region={meta.get('region_id')} id={c.get('id')} sim={c.get('sim'):.3f}"
        )
        text = c.get("text", "").strip()
        ctx_parts.append(header + "\n" + text)
    ctx = "\n\n".join(ctx_parts)

    system = (
        "Ты — ассистент, отвечающий строго на основе предоставленного контекста. "
        "Если ответа нет в контексте — скажи об этом честно. В конце ответа укажи источники (file и page)."
    )
    user = f"Вопрос: {query}\n\nКонтекст:\n{ctx}"

    resp = client.chat.completions.create(
        model=chat_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
    )
    return resp.choices[0].message.content.strip()


def main():
    p = argparse.ArgumentParser(description="RAG: retrieve top-k and answer with OpenAI chat model")
    p.add_argument("--index", default="out/openai_embeddings.ndjson")
    p.add_argument("--query", required=True)
    p.add_argument("--k", type=int, default=5)
    p.add_argument("--embed-model", default="text-embedding-3-large")
    p.add_argument("--chat-model", default="gpt-4o-mini")
    args = p.parse_args()

    items = load_ndjson(Path(args.index))
    qv = embed_query_openai(args.query, model=args.embed_model)

    scored = []
    for it in items:
        sim = cosine_sim(qv, it["vector"])  # type: ignore
        scored.append((sim, it))
    scored.sort(key=lambda x: x[0], reverse=True)

    top = []
    for sim, it in scored[: args.k]:
        it2 = dict(it)
        it2["sim"] = float(sim)
        top.append(it2)

    ans = answer_with_openai(args.query, top, chat_model=args.chat_model)
    print(ans)


if __name__ == "__main__":
    main()
