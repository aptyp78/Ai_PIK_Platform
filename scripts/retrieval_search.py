#!/usr/bin/env python3
import argparse
import os
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


def embed_query_openclip(text: str, model_name: str = "ViT-B-32", pretrained: str = "laion2b_s34b_b79k") -> List[float]:
    try:
        import open_clip  # type: ignore
        import torch  # type: ignore
    except Exception:
        raise SystemExit("open_clip/torch required for --with-images. Install open-clip-torch and torch.")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, _, preprocess = open_clip.create_model_and_transforms(model_name, pretrained=pretrained, device=device)
    tokenizer = open_clip.get_tokenizer(model_name)
    with torch.no_grad():
        tok = tokenizer([text])
        tok = {k: v.to(device) for k, v in tok.items()} if isinstance(tok, dict) else tok.to(device)
        feats = model.encode_text(tok)
        feats = feats / feats.norm(dim=-1, keepdim=True)
    return feats[0].cpu().tolist()  # type: ignore


def main():
    p = argparse.ArgumentParser(description="Cosine search over precomputed OpenAI embeddings (NDJSON)")
    p.add_argument("--index", default="out/openai_embeddings.ndjson", help="Path to NDJSON with vectors")
    p.add_argument("--query", required=True, help="Search query (any language)")
    p.add_argument("--k", type=int, default=5, help="Top K results")
    p.add_argument("--model", default="text-embedding-3-large", help="OpenAI embedding model for the query")
    p.add_argument("--prefer-visual", action="store_true", help="Upweight VisualCaption/VisualFact types")
    p.add_argument("--type-weights", default=None, help="Comma list, e.g., Text=1,VisualCaption=1.1,VisualFact=1.05")
    p.add_argument("--with-images", action="store_true", help="Blend OpenCLIP image vectors into ranking")
    p.add_argument("--image-model-name", default="ViT-B-32")
    p.add_argument("--image-pretrained", default="laion2b_s34b_b79k")
    p.add_argument("--image-weight", type=float, default=0.5, help="Weight multiplier for image scores in blend")
    args = p.parse_args()

    items = load_ndjson(Path(args.index))
    qvec = embed_query_openai(args.query, model=args.model)
    qclip = None
    if args.with_images:
        try:
            qclip = embed_query_openclip(args.query, model_name=args.image_model_name, pretrained=args.image_pretrained)
        except SystemExit as e:
            print(str(e))
            args.with_images = False

    # parse type weights
    weights = {"Text": 1.0, "VisualCaption": 1.0, "VisualFact": 1.0, "Image": 0.95, "Table": 1.0}
    if args.prefer_visual:
        weights.update({"VisualCaption": 1.1, "VisualFact": 1.05})
    if args.type_weights:
        for tok in args.type_weights.split(","):
            if not tok.strip():
                continue
            if "=" in tok:
                k, v = tok.split("=", 1)
                try:
                    weights[k.strip()] = float(v)
                except Exception:
                    pass
    # tag weights
    p_tag = p.add_argument_group("tag boost")
    # For CLI parity, parse from env if set
    tag_weights_env = os.environ.get("TAG_WEIGHTS")
    # reasonable defaults if none provided
    tag_weights = {"Canvas": 1.06, "Assessment": 1.05, "Diagram": 1.04, "Pillar": 1.06, "Layer": 1.05}
    if tag_weights_env:
        for tok in tag_weights_env.split(","):
            if "=" in tok:
                k, v = tok.split("=", 1)
                try:
                    tag_weights[k.strip()] = float(v)
                except Exception:
                    pass

    scored: List[Tuple[float, dict]] = []
    for it in items:
        m = it.get("meta", {})
        t = m.get("type")
        provider = it.get("provider")
        score = 0.0
        if provider == "open_clip" and args.with_images and qclip is not None:
            score = cosine_sim(qclip, it["vector"]) * args.image_weight  # type: ignore
        else:
            sim = cosine_sim(qvec, it["vector"])  # type: ignore
            w = weights.get(t, 1.0)
            tw = 1.0
            tags = m.get("tags") or []
            if isinstance(tags, list) and tags:
                for tg in tags:
                    tw = max(tw, tag_weights.get(tg, 1.0))
            score = sim * w * tw
        scored.append((score, it))
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
