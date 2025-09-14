#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path
from typing import Dict, Iterable, List


def iter_text_elements(path: Path) -> Iterable[Dict]:
    data = json.loads(path.read_text())
    wanted = {
        "Title",
        "NarrativeText",
        "ListItem",
        "Header",
        "Footer",
        "Table",
        "Image",
    }
    for el in data:
        if el.get("type") in wanted:
            t = (el.get("text") or "").strip()
            if t:
                md = el.get("metadata", {}) or {}
                yield {
                    "text": t,
                    "page": md.get("page_number"),
                    "element_id": el.get("element_id"),
                    "filename": md.get("filename"),
                    "type": el.get("type"),
                }


def chunk_elements(elems: Iterable[Dict], max_chars: int = 2500) -> Iterable[Dict]:
    buf: List[Dict] = []
    size = 0
    for el in elems:
        t = el["text"]
        if size and size + 1 + len(t) > max_chars:
            yield {
                "text": "\n".join(x["text"] for x in buf),
                "meta": {**{k: buf[0].get(k) for k in ("page", "element_id", "filename", "type")}, "span": len(buf)},
            }
            buf, size = [], 0
        buf.append(el)
        size += len(t) + 1
    if buf:
        yield {
            "text": "\n".join(x["text"] for x in buf),
            "meta": {**{k: buf[0].get(k) for k in ("page", "element_id", "filename", "type")}, "span": len(buf)},
        }


def embed_openai_texts(chunks: List[Dict], model: str = "text-embedding-3-large", batch: int = 64) -> List[List[float]]:
    try:
        from openai import OpenAI  # type: ignore
    except Exception as e:
        raise SystemExit(f"openai package not installed: {e}. Try: pip install openai>=1.40.0")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY env var is required.")

    client = OpenAI(api_key=api_key)
    inputs = [c["text"] for c in chunks]
    embs: List[List[float]] = []
    for i in range(0, len(inputs), batch):
        resp = client.embeddings.create(model=model, input=inputs[i : i + batch])
        embs.extend([d.embedding for d in resp.data])
    return embs


def main() -> None:
    parser = argparse.ArgumentParser(description="Embed Unstructured JSON and compare providers.")
    parser.add_argument(
        "--file",
        default=str(Path.home() / "GCS/pik_result_bucket/Qdrant_Destination/playbooks/PIK - Expert Guide - Platform IT Architecture - Playbook - v11.pdf.json"),
        help="Path to Unstructured partition JSON.",
    )
    parser.add_argument("--outdir", default="out", help="Output directory.")
    parser.add_argument("--max-chars", type=int, default=2500, help="Max characters per chunk.")
    parser.add_argument(
        "--openai-model",
        default="text-embedding-3-large",
        help="OpenAI embedding model (e.g., text-embedding-3-large).",
    )
    args = parser.parse_args()

    src = Path(args.file)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    elements = list(iter_text_elements(src))
    chunks = list(chunk_elements(elements, max_chars=args.max_chars))
    print(f"Loaded {len(elements)} elements -> {len(chunks)} chunks")

    # OpenAI embeddings
    print(f"Embedding with OpenAI: {args.openai_model} ...")
    openai_vectors = embed_openai_texts(chunks, model=args.openai_model)
    if len(openai_vectors) != len(chunks):
        raise RuntimeError("Embedding count mismatch for OpenAI")

    openai_out = outdir / "openai_embeddings.ndjson"
    with openai_out, open(openai_out, "w") as f:
        for i, (c, vec) in enumerate(zip(chunks, openai_vectors)):
            rec = {
                "id": i,
                "text": c["text"],
                "vector": vec,
                "meta": c["meta"],
                "provider": "openai",
                "model": args.openai_model,
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"Wrote OpenAI embeddings -> {openai_out}")

    # Sonar note (no embeddings endpoint)
    sonar_note = {
        "note": (
            "Perplexity Sonar (e.g., 'sonar-medium') does not expose an embeddings endpoint. "
            "Use Sonar for generation/reranking, or choose an alternative embeddings model (e.g., Cohere 'embed-english-v3.0' or Voyage 'voyage-2')."
        )
    }
    (outdir / "sonar_embeddings.NOT_SUPPORTED.json").write_text(json.dumps(sonar_note, ensure_ascii=False, indent=2))
    print("Sonar embeddings: not supported by API; wrote explanatory note.")


if __name__ == "__main__":
    main()

