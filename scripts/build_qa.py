#!/usr/bin/env python3
import argparse
import json
import math
from pathlib import Path
from typing import List, Dict, Tuple


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


def cosine_sim(a: List[float], b: List[float]) -> float:
    na, nb = norm(a), norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return dot(a, b) / (na * nb)


def embed_query(text: str, model: str) -> List[float]:
    from openai import OpenAI

    client = OpenAI()
    resp = client.embeddings.create(model=model, input=[text])
    return resp.data[0].embedding


def answer_openai(query: str, contexts: List[Dict], chat_model: str) -> str:
    from openai import OpenAI

    client = OpenAI()
    ctx_parts = []
    for i, c in enumerate(contexts, start=1):
        m = c.get("meta", {})
        header = f"[CTX {i}] file={m.get('filename')} page={m.get('page')} id={c.get('id')} sim={c.get('sim'):.3f}"
        ctx_parts.append(header + "\n" + c.get("text", "").strip())
    ctx = "\n\n".join(ctx_parts)

    system = (
        "Ты — ассистент, отвечающий строго на основе предоставленного контекста. "
        "Если ответа нет в контексте — скажи об этом и не выдумывай. В конце ответа укажи источники (file и page)."
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


def main() -> None:
    ap = argparse.ArgumentParser(description="Build QA file for all eval queries using RAG over precomputed embeddings")
    ap.add_argument("--index", default="out/openai_embeddings.ndjson")
    ap.add_argument("--eval", default="eval/queries.jsonl")
    ap.add_argument("--out-jsonl", default="eval/qa.jsonl")
    ap.add_argument("--out-md", default="eval/qa.md")
    ap.add_argument("--k", type=int, default=3)
    ap.add_argument("--embed-model", default="text-embedding-3-large")
    ap.add_argument("--chat-model", default="gpt-4o-mini")
    args = ap.parse_args()

    index = load_ndjson(Path(args.index))
    eval_rows = [json.loads(l) for l in Path(args.eval).read_text().splitlines() if l.strip()]

    outj = Path(args.out_jsonl)
    outm = Path(args.out_md)
    outj.parent.mkdir(parents=True, exist_ok=True)

    with open(outj, "w") as fj, open(outm, "w") as fm:
        for i, row in enumerate(eval_rows, start=1):
            query = row["query"]
            qv = embed_query(query, model=args.embed_model)
            scored: List[Tuple[float, Dict]] = []
            for it in index:
                sim = cosine_sim(qv, it["vector"])  # type: ignore
                it2 = dict(it)
                it2["sim"] = float(sim)
                scored.append((sim, it2))
            scored.sort(key=lambda x: x[0], reverse=True)
            top = [it for _, it in scored[: args.k]]

            answer = answer_openai(query, top, chat_model=args.chat_model)
            rec = {
                "idx": i,
                "query": query,
                "answer": answer,
                "sources": [
                    {
                        "id": it.get("id"),
                        "page": it.get("meta", {}).get("page"),
                        "filename": it.get("meta", {}).get("filename"),
                        "sim": it.get("sim"),
                    }
                    for it in top
                ],
            }
            fj.write(json.dumps(rec, ensure_ascii=False) + "\n")

            fm.write(f"Q{i}: {query}\n")
            fm.write(f"A{i}: {answer}\n")
            fm.write("Sources:\n")
            for s in rec["sources"]:
                fm.write(f"- id={s['id']} page={s['page']} file={s['filename']} sim={s['sim']:.3f}\n")
            fm.write("\n")

    print(f"Wrote {outj} and {outm}")


if __name__ == "__main__":
    main()
