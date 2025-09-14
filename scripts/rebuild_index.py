#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

WANTED_TYPES = {"Title", "NarrativeText", "ListItem", "Header", "Footer", "Table", "Image"}
SKIP_TYPES = {"PageBreak"}


def iter_text_elements(path: Path) -> Iterable[Dict]:
    data = json.loads(path.read_text())
    for el in data:
        t = (el.get("type") or "").strip()
        if t in SKIP_TYPES:
            continue
        if t not in WANTED_TYPES:
            continue
        text = (el.get("text") or "").strip()
        if not text:
            continue
        # Filter noisy OCR images
        if t == "Image" and len(text) < 180:
            continue
        md = el.get("metadata", {}) or {}
        yield {
            "type": t,
            "text": text,
            "page": md.get("page_number"),
            "element_id": el.get("element_id"),
            "filename": md.get("filename") or path.name,
            "source_file": str(path),
        }


def chunk_with_overlap(elems: Iterable[Dict], max_chars: int = 1400, overlap_chars: int = 180) -> Iterable[Dict]:
    buf: List[Dict] = []
    size = 0
    tail_text = ""
    for el in elems:
        t = el["text"]
        add_len = len(t) + (1 if buf else 0)
        if size and size + add_len > max_chars:
            text = "\n".join(x["text"] for x in buf)
            meta = {k: buf[0].get(k) for k in ("page", "element_id", "filename", "type", "source_file")}
            meta["span"] = len(buf)
            yield {"text": text, "meta": meta}
            # prepare overlap tail
            if overlap_chars > 0:
                tail_text = text[-overlap_chars:]
                buf = [{"text": tail_text, **buf[-1]}]
                size = len(tail_text)
            else:
                buf, size = [], 0
        # append current
        if buf:
            size += 1
        buf.append(el)
        size += len(t)
    if buf:
        text = "\n".join(x["text"] for x in buf)
        meta = {k: buf[0].get(k) for k in ("page", "element_id", "filename", "type", "source_file")}
        meta["span"] = len(buf)
        yield {"text": text, "meta": meta}


def embed_openai(chunks: List[Dict], model: str, batch: int = 64) -> List[List[float]]:
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is required")
    client = OpenAI(api_key=api_key)
    inputs = [c["text"] for c in chunks]
    out: List[List[float]] = []
    for i in range(0, len(inputs), batch):
        resp = client.embeddings.create(model=model, input=inputs[i:i+batch])
        out.extend([d.embedding for d in resp.data])
    return out


def main():
    ap = argparse.ArgumentParser(description="Rebuild embeddings index from multiple Unstructured JSON files")
    ap.add_argument("--out", default="out/openai_embeddings.ndjson")
    ap.add_argument("--model", default="text-embedding-3-large")
    ap.add_argument("--max-chars", type=int, default=1400)
    ap.add_argument("--overlap", type=int, default=180)
    ap.add_argument("files", nargs="+", help="List of JSON files")
    args = ap.parse_args()

    # Collect elements from each file in order
    all_chunks: List[Dict] = []
    for fp in args.files:
        p = Path(fp)
        elems = list(iter_text_elements(p))
        if not elems:
            continue
        chunks = list(chunk_with_overlap(elems, max_chars=args.max_chars, overlap_chars=args.overlap))
        all_chunks.extend(chunks)
    if not all_chunks:
        raise SystemExit("No chunks collected")

    vecs = embed_openai(all_chunks, model=args.model)
    if len(vecs) != len(all_chunks):
        raise SystemExit("Embedding count mismatch")

    outp = Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    with open(outp, "w") as f:
        for i, (c, v) in enumerate(zip(all_chunks, vecs)):
            rec = {
                "id": i,
                "text": c["text"],
                "vector": v,
                "meta": c["meta"],
                "provider": "openai",
                "model": args.model,
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"Wrote {len(all_chunks)} chunks to {outp}")


if __name__ == "__main__":
    main()
