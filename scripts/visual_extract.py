#!/usr/bin/env python3
import argparse
import base64
import json
import os
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


WANTED_TEXT_TYPES = {"Title", "NarrativeText", "ListItem", "Header", "Footer", "Table"}


def load_page_material(path: Path, pages: Optional[List[int]] = None) -> Dict[int, Dict[str, object]]:
    """
    Load Unstructured JSON and collect per-page material:
    - page_text: concatenated textual elements for the page
    - images_b64: list of base64 strings if present on the page
    Returns mapping page -> {page_text: str, images_b64: List[str]}
    """
    data = json.loads(path.read_text())
    out: Dict[int, Dict[str, object]] = {}
    for el in data:
        md = el.get("metadata", {}) or {}
        page = md.get("page_number")
        if page is None:
            continue
        if pages and int(page) not in pages:
            continue

        rec = out.setdefault(int(page), {"page_text": [], "images_b64": []})

        # Text aggregation
        etype = (el.get("type") or "").strip()
        if etype in WANTED_TEXT_TYPES:
            t = (el.get("text") or "").strip()
            if t:
                rec["page_text"].append(t)  # type: ignore

        # Image collection — common fields seen in Unstructured outputs
        b64 = None
        if isinstance(el.get("image_base64"), str):
            b64 = el.get("image_base64")
        elif isinstance(md.get("image_base64"), str):
            b64 = md.get("image_base64")
        elif isinstance(el.get("image"), str) and el.get("image", "").startswith("data:image/"):
            # already a data URL
            b64 = el.get("image").split(",", 1)[-1]
        if b64:
            try:
                # sanity check decode
                base64.b64decode(b64, validate=True)
                rec["images_b64"].append(b64)  # type: ignore
            except Exception:
                pass

    # finalize page_text to string
    for p, rec in out.items():
        txts = rec.get("page_text") or []
        if isinstance(txts, list):
            rec["page_text"] = "\n".join(txts)
    return out


def openai_client():
    try:
        from openai import OpenAI  # type: ignore
    except Exception as e:
        raise SystemExit(f"openai package not installed: {e}. Try: pip install openai>=1.40.0")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY env var is required")
    return OpenAI(api_key=api_key)


def generate_caption_and_struct(
    client,
    page_text: str,
    images_b64: List[str],
    model: str = "gpt-4o",
) -> Tuple[str, Dict]:
    """
    Use GPT-4o to produce a rich caption and a normalized struct JSON.
    If image is available, pass it; otherwise rely on page_text only.
    """
    sys_prompt = (
        "You are a vision+text analyst. Produce a concise, informative caption for a platform architecture visual, "
        "then emit a normalized JSON structure capturing key elements. If the visual represents a Canvas, Assessment, or Diagram, choose the closest type."
    )
    # Build user content
    content: List[Dict[str, object]] = []
    # include up to 3 images for richer context
    for b64 in images_b64[:3]:
        data_url = f"data:image/png;base64,{b64}"
        content.append({"type": "image_url", "image_url": {"url": data_url}})
    # Provide page text as auxiliary input
    if page_text:
        content.append(
            {
                "type": "text",
                "text": (
                    "Auxiliary OCR/Text from the same page (use as hints, avoid quoting verbatim):\n" + page_text[:6000]
                ),
            }
        )

    # Ask for caption
    caption_instr = (
        "Task 1: Return a 2-4 sentence caption describing the visual: layers/pillars, key components, relations, headings."
    )
    # Ask for struct JSON with type autodetect
    struct_instr = (
        "Task 2: Return ONLY a JSON object with fields: "
        "{artifact_type: one of [Canvas, Assessment, Diagram, Unknown], "
        "Canvas?: {layers: [..], components: [..], personas: [..], journey: [..], relations: [..]}, "
        "Assessment?: {pillars: {Operational, Security, Reliability, Performance, Cost}, criteria: [..], questions: [..], scoring_fields: [..]}, "
        "Diagram?: {entities: [..], edges: [..], legend: [..], groups: [..]}}. "
        "Keep arrays concise and canonicalize layer/pillar names if possible."
    )

    # First, caption
    cap_resp = client.chat.completions.create(
        model=model,
        temperature=0.1,
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": content + [{"type": "text", "text": caption_instr}]},
        ],
    )
    caption = (cap_resp.choices[0].message.content or "").strip()

    # Then, struct
    struct_resp = client.chat.completions.create(
        model=model,
        temperature=0.1,
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": content + [{"type": "text", "text": struct_instr}]},
        ],
    )
    struct_txt = (struct_resp.choices[0].message.content or "{}").strip()
    try:
        # Some models might wrap JSON in code fences – strip if present
        if struct_txt.startswith("```"):
            struct_txt = struct_txt.strip("`\n").split("\n", 1)[-1]
            if struct_txt.startswith("json\n"):
                struct_txt = struct_txt[5:]
        struct = json.loads(struct_txt)
        if not isinstance(struct, dict):
            struct = {"artifact_type": "Unknown", "raw": struct}
    except Exception:
        struct = {"artifact_type": "Unknown", "raw_text": struct_txt}

    return caption, struct


def synthesize_facts(struct: Dict) -> Tuple[List[str], List[Dict]]:
    """
    Return two representations:
    - flat_txt: simple human-readable lines for backwards compatibility
    - triples: structured JSONL-like items {type, subject, predicate, object, tags}
    """
    flat: List[str] = []
    triples: List[Dict] = []
    at = (struct.get("artifact_type") or "Unknown").strip()
    if at == "Canvas":
        canvas = struct.get("Canvas", {}) if isinstance(struct.get("Canvas"), dict) else {}
        layers = canvas.get("layers", []) if isinstance(canvas, dict) else []
        components = canvas.get("components", []) if isinstance(canvas, dict) else []
        for l in layers:
            flat.append(f"Layer={l}")
            triples.append({"type": "Layer", "subject": l, "predicate": "is_a", "object": "Layer", "tags": ["Canvas"]})
        for c in components:
            flat.append(f"Component={c}")
            triples.append({"type": "Component", "subject": c, "predicate": "appears_in", "object": "Canvas", "tags": []})
    elif at == "Assessment":
        assess = struct.get("Assessment", {}) if isinstance(struct.get("Assessment"), dict) else {}
        pillars = assess.get("pillars", {}) if isinstance(assess, dict) else {}
        for p in list(pillars.keys()):
            flat.append(f"Pillar={p}")
            triples.append({"type": "Pillar", "subject": p, "predicate": "is_a", "object": "Pillar", "tags": ["Assessment"]})
        criteria = assess.get("criteria", []) if isinstance(assess, dict) else []
        for cr in criteria:
            flat.append(f"Criterion={cr}")
            triples.append({"type": "Criterion", "subject": cr, "predicate": "belongs_to", "object": "Assessment", "tags": []})
    elif at == "Diagram":
        diagram = struct.get("Diagram", {}) if isinstance(struct.get("Diagram"), dict) else {}
        entities = diagram.get("entities", []) if isinstance(diagram, dict) else []
        for e in entities:
            flat.append(f"Entity={e}")
            triples.append({"type": "Entity", "subject": e, "predicate": "appears_in", "object": "Diagram", "tags": []})
    return [s for s in (t.strip() for t in flat) if s], triples


def save_image(path: Path, b64: str) -> None:
    try:
        data = base64.b64decode(b64)
        path.write_bytes(data)
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser(description="Extract visual caption/struct/facts per page using GPT-4o")
    ap.add_argument("--json", required=True, help="Path to Unstructured JSON source")
    ap.add_argument("--pages", nargs="+", type=int, help="Printed page numbers to process")
    ap.add_argument("--outdir", default="out/visual/pages", help="Output directory")
    ap.add_argument("--chat-model", default="gpt-4o-mini", help="Vision-capable model (e.g., gpt-4o or gpt-4o-mini)")
    args = ap.parse_args()

    src = Path(args.json)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    pages = [int(p) for p in args.pages]
    pages_mat = load_page_material(src, pages)

    client = openai_client()

    for page in sorted(pages_mat.keys()):
        rec = pages_mat[page]
        page_text = rec.get("page_text", "") or ""
        images = rec.get("images_b64", []) or []
        # Generate
        caption, struct = generate_caption_and_struct(client, str(page_text), list(images), model=args.chat_model)
        flat_facts, triples = synthesize_facts(struct)

        # Save artifacts
        base = outdir / f"{page}"
        (base.parent).mkdir(parents=True, exist_ok=True)
        (outdir / f"{page}.caption.txt").write_text(caption.strip() + "\n", encoding="utf-8")
        (outdir / f"{page}.struct.json").write_text(json.dumps(struct, ensure_ascii=False, indent=2))
        (outdir / f"{page}.facts.txt").write_text("\n".join(flat_facts) + ("\n" if flat_facts else ""), encoding="utf-8")
        # write structured facts JSONL
        with open(outdir / f"{page}.facts.jsonl", "w", encoding="utf-8") as jf:
            for obj in triples:
                jf.write(json.dumps(obj, ensure_ascii=False) + "\n")
        # save first image as preview if any
        if images:
            save_image(outdir / f"{page}.png", images[0])
        print(f"Wrote artifacts for page {page} -> {outdir}")


if __name__ == "__main__":
    main()
