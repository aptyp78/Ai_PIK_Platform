#!/usr/bin/env python3
import argparse
import base64
import json
import math
import re
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None


def openai_client():
    from openai import OpenAI
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is required")
    return OpenAI(api_key=api_key)


def ensure_png(path: Path, caption: str, text: str) -> None:
    try:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore
    except Exception:
        return
    W, H = 1000, 600
    im = Image.new("RGB", (W, H), (255, 255, 255))
    draw = ImageDraw.Draw(im)
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None
    body = (caption or text or "Region (no image)").strip()
    max_w = W - 80
    words = body.split()
    lines = []
    cur = ""
    for w in words:
        test = (cur + " " + w).strip()
        if draw.textlength(test, font=font) <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    y = 40
    for ln in lines[:14]:
        draw.text((40, y), ln, fill=(20, 20, 20), font=font)
        y += 40
    im.save(path)

def ocr_from_b64(image_b64: str) -> str:
    try:
        import io
        from PIL import Image  # type: ignore
        import pytesseract  # type: ignore
        data = base64.b64decode(image_b64)
        im = Image.open(io.BytesIO(data)).convert("RGB")
        txt = pytesseract.image_to_string(im)
        return txt.strip()
    except Exception:
        return ""


def _postprocess_struct(obj: Dict[str, Any]) -> Dict[str, Any]:
    # Normalize common variants into our schema
    if not isinstance(obj, dict):
        return {"artifact_type": "Unknown", "raw_text": str(obj)}
    out = dict(obj)
    # Map 'type' -> artifact_type when present
    t = (out.get("type") or out.get("artifact_type") or "").strip()
    if t and not out.get("artifact_type"):
        out["artifact_type"] = t if t in {"Canvas", "Assessment", "Diagram"} else "Unknown"
    # Ensure top-level keys exist
    for k in ("Canvas", "Assessment", "Diagram"):
        if k not in out:
            out[k] = out.get(k) if isinstance(out.get(k), dict) else {}
    return out


def _is_gpt5(model: str) -> bool:
    try:
        return str(model).strip().lower().startswith("gpt-5")
    except Exception:
        return False


# ---------- PVStack + weighting helpers ----------
PVSTACK_LAYERS = ["Experience", "Interactions", "Data", "Infrastructure"]


def _load_synonyms(path: Path) -> Dict[str, Any]:
    default: Dict[str, Any] = {
        "PVStack": {
            "Experience": ["Engagement", "User Experience", "UX"],
            "Interactions": ["Ecosystem Connectivity", "Connectivity", "Interaction"],
            "Data": ["Intelligence", "Analytics", "Insights"],
            "Infrastructure": ["Platform Infrastructure", "Infra"],
        },
        "Roles": {
            "Orchestrator": ["Owner", "Platform Owner"],
            "Producer": ["Supplier", "Provider"],
            "Partner(Enabler)": ["Enabler", "Partner"],
            "Consumer": ["Customer", "User"],
        },
        "VisualObjects": {
            "Контрольная точка (Control Point)": ["Control Point", "Контрольная точка"],
            "Матчинг‑контур": ["Matching contour", "Match loop"],
            "Ценностное предложение": ["Value Proposition"],
            "JTBD‑ядро": ["JTBD core", "JTBD"],
            "Карта экосистемы": ["Ecosystem Map"],
            "Онбординг": ["Onboarding"],
            "Роадмэп 3 горизонтов": ["Three Horizons Roadmap", "3 Horizons"],
        },
        "Keywords": [
            "liquidity",
            "onboarding",
            "activation",
            "nfx",
            "network effects",
            "pricing",
            "take rate",
            "value",
            "jtbd",
            "roadmap",
            "ecosystem",
            "growth",
            "governance",
            "risk",
            "kpi",
            "data",
            "flywheel",
        ],
    }
    try:
        if path.exists() and yaml is not None:
            with open(path, "r", encoding="utf-8") as f:
                user_cfg = yaml.safe_load(f) or {}
            # shallow-merge known sections
            for k in ("PVStack", "Roles", "VisualObjects", "Keywords"):
                if k in user_cfg and isinstance(user_cfg[k], (dict, list)):
                    default[k] = user_cfg[k]
    except Exception:
        pass
    return default


def _make_layer_canon_map(syn: Dict[str, Any]) -> Dict[str, str]:
    m: Dict[str, str] = {}
    pv = syn.get("PVStack", {}) or {}
    for canon, alts in pv.items():
        m[canon.lower()] = canon
        if isinstance(alts, list):
            for a in alts:
                m[str(a).lower()] = canon
    return m


def canonicalize_layers(layers: List[str], syn: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    m = _make_layer_canon_map(syn)
    for l in layers or []:
        key = str(l).strip()
        canon = m.get(key.lower())
        if not canon and key.lower() in {"engagement", "intelligence", "ecosystem connectivity"}:
            # Back-compat for earlier schema
            alt_map = {
                "engagement": "Experience",
                "intelligence": "Data",
                "ecosystem connectivity": "Interactions",
            }
            canon = alt_map.get(key.lower(), key)
        out.append(canon or key)
    # keep order but filter to PVSTACK when close set was intended
    uniq = []
    for l in out:
        if l not in uniq:
            uniq.append(l)
    return uniq


def profile_weights(profile: str) -> Tuple[float, float, float, float]:
    p = (profile or "").strip().lower()
    if p in {"discover", "launch", "discover/launch"}:
        return (0.45, 0.15, 0.30, 0.10)
    if p in {"growth", "scale", "growth/scale"}:
        return (0.55, 0.25, 0.15, 0.05)
    if p in {"governance", "risk", "governance/risks"}:
        return (0.40, 0.20, 0.35, 0.05)
    # default to Discover/Launch
    return (0.45, 0.15, 0.30, 0.10)


def choose_profile(struct: Dict[str, Any], ocr_text: str) -> str:
    tag = (struct.get("Tagging") or {}).get("DoubleLoop") if isinstance(struct.get("Tagging"), dict) else None
    t = str(tag or "").strip().lower()
    if t in {"discover", "launch"}:
        return "discover"
    if t in {"growth", "scale"}:
        return "growth"
    low = (ocr_text or "").lower()
    # growth hint
    if re.search(r"\b(growth|scale|scaling|nfx|network effects|liquidity|activation|referral)\b", low):
        return "growth"
    # governance hint
    if re.search(r"\b(governance|risk|compliance|policy|moderation|ethics|transparency)\b", low):
        return "governance"
    return "discover"


def _flatten_lexicon(synonyms: Dict[str, Any]) -> List[str]:
    lex: List[str] = []
    # Keywords (free list)
    for k in (synonyms.get("Keywords") or []):
        try:
            s = str(k).strip()
            if s:
                lex.append(s)
        except Exception:
            pass
    # PVStack
    for key, alts in (synonyms.get("PVStack") or {}).items():
        try:
            lex.append(str(key))
            for a in (alts or []):
                lex.append(str(a))
        except Exception:
            pass
    # Roles
    for key, alts in (synonyms.get("Roles") or {}).items():
        try:
            lex.append(str(key))
            for a in (alts or []):
                lex.append(str(a))
        except Exception:
            pass
    # Groups (24 semantic groups)
    for key, alts in (synonyms.get("Groups") or {}).items():
        try:
            lex.append(str(key))
            for a in (alts or []):
                lex.append(str(a))
        except Exception:
            pass
    # Visual objects names and synonyms
    for key, alts in (synonyms.get("VisualObjects") or {}).items():
        try:
            lex.append(str(key))
            for a in (alts or []):
                lex.append(str(a))
        except Exception:
            pass
    # deduplicate, preserve order
    seen = set()
    uni: List[str] = []
    for t in lex:
        tl = t.lower()
        if tl not in seen:
            seen.add(tl)
            uni.append(t)
    return uni


def score_text(ocr_text: str, synonyms: Dict[str, Any]) -> float:
    if not ocr_text:
        return 0.0
    txt = ocr_text.lower()
    lexicon = _flatten_lexicon(synonyms)
    hits = 0
    for kw in lexicon:
        if not kw:
            continue
        if re.search(r"\b" + re.escape(kw.lower()) + r"\b", txt):
            hits += 1
            if hits >= 5:
                break
    # simple saturation curve (up to 5 hits)
    return max(0.0, min(1.0, hits / 5.0))


def score_layout(layout: Dict[str, Any]) -> float:
    z = (layout or {}).get("zone") or ""
    z = str(z)
    base = {
        "center": 1.0,
        "right": 0.9,
        "top-right": 0.85,
        "top-left": 0.8,
        "top": 0.75,
        "left": 0.7,
        "bottom-right": 0.7,
        "bottom": 0.65,
        "bottom-left": 0.6,
    }
    return base.get(z, 0.6)


def base_weight_for_visual_object(name: str) -> float:
    n = (name or "").strip().lower()
    table = {
        "контрольная точка (control point)": 1.0,
        "control point": 1.0,
        "матчинг‑контур": 0.9,
        "matching contour": 0.9,
        "ценностное предложение": 0.8,
        "value proposition": 0.8,
        "jtbd‑ядро": 0.8,
        "jtbd": 0.8,
        "карта экосистемы": 0.8,
        "ecosystem map": 0.8,
        "build–buy–partner–join": 0.8,
        "onboarding": 0.8,
        "онбординг": 0.8,
        "пул ценности": 0.7,
        "value pool": 0.7,
        "модуль платформенного сервиса": 0.7,
        "роадмэп 3 горизонтов": 0.6,
        "three horizons roadmap": 0.6,
        "визия платформы": 0.6,
        "позиционирование": 0.7,
        "где играть": 0.7,
        "как побеждать": 0.7,
        "кластер предложения": 0.6,
        "сегмент спроса": 0.6,
        "матрица коопетиции": 0.6,
        "соседние рынки": 0.6,
    }
    return table.get(n, 0.6)


def llm_analyze(client, text: str, image_b64: str, model: str) -> (str, Dict[str, Any]):
    content = []
    if image_b64:
        data_url = f"data:image/png;base64,{image_b64}"
        content.append({"type": "image_url", "image_url": {"url": data_url}})
    if text:
        content.append({"type": "text", "text": f"Region OCR/Text (may be noisy):\n{text[:4000]}"})

    sys = (
        "You are a precise vision+text analyst. For the region, produce: "
        "(1) a concise caption (1–2 sentences) and (2) a STRICT JSON object describing the artifact."
    )
    # caption
    cap_kwargs = {
        "model": model,
        "messages": [
            {"role": "system", "content": sys},
            {"role": "user", "content": content + [{"type": "text", "text": "Task 1: Return a 1-2 sentence caption."}]},
        ],
    }
    if not _is_gpt5(model):
        cap_kwargs["temperature"] = 0.1
    cap = client.chat.completions.create(**cap_kwargs)
    caption = (cap.choices[0].message.content or "").strip()

    # struct
    struct_instr = (
        "Task 2: Return ONLY a JSON object with this schema: "
        "{artifact_type: 'Canvas'|'Assessment'|'Diagram', "
        " Canvas?: {layers?: string[], components?: string[], personas?: string[], journey?: string[], relations?: string[]}, "
        " Assessment?: {pillars?: {Operational?:any, Security?:any, Reliability?:any, Performance?:any, Cost?:any}, criteria?: string[]}, "
        " Diagram?: {entities?: string[], edges?: string[], legend?: string[], groups?: string[]}, "
        " Tagging?: {DoubleLoop?: 'Discover'|'Launch'|'Growth'|'Scale', Level?: 'Portfolio(L1)'|'Market(L2)'|'Platform(L3)', Role?: 'Orchestrator'|'Producer'|'Partner(Enabler)'|'Consumer', Zone?: string, VisualObject?: string, Sustainability?: {People?:boolean, Planet?:boolean, Profit?:boolean, SDG?: string[]}}, "
        " CanvasName?: string, Integration?: {Horizontal?: string[], Vertical?: string[]} } "
        "Use ONLY canonical Canvas.layers (PVStack) if applicable: ['Experience','Interactions','Data','Infrastructure']."
    )
    st_kwargs = {
        "model": model,
        "messages": [
            {"role": "system", "content": sys},
            {"role": "user", "content": content + [{"type": "text", "text": struct_instr}]},
        ],
    }
    if not _is_gpt5(model):
        st_kwargs["temperature"] = 0.1
        st_kwargs["response_format"] = {"type": "json_object"}
    st = client.chat.completions.create(**st_kwargs)
    raw = (st.choices[0].message.content or "{}").strip()
    try:
        struct = json.loads(raw)
    except Exception:
        struct = {"artifact_type": "Unknown", "raw_text": raw}
    struct = _postprocess_struct(struct)
    return caption, struct


def synthesize_triples(struct: Dict[str, Any], page: int, rid: int, default_conf: Optional[float] = None) -> List[Dict[str, Any]]:
    triples: List[Dict[str, Any]] = []
    at = (struct.get("artifact_type") or "").strip()
    def make_id(i):
        return f"t-p{page}-r{rid}-n{i}"
    i = 0
    if at == "Canvas":
        cv = struct.get("Canvas", {}) if isinstance(struct.get("Canvas"), dict) else {}
        for l in cv.get("layers", []) or []:
            i += 1
            triples.append({"id": make_id(i), "subject": {"name": l, "type": "Layer"}, "predicate": "is_a", "object": {"name": "Layer", "type": "Class"}, "tags": ["Canvas"], "confidence": (default_conf if default_conf is not None else 0.80)})
        for c in cv.get("components", []) or []:
            i += 1
            triples.append({"id": make_id(i), "subject": {"name": c, "type": "Component"}, "predicate": "appears_in", "object": {"name": "Canvas", "type": "Artifact"}, "tags": ["Canvas"], "confidence": (default_conf if default_conf is not None else 0.75)})
    elif at == "Assessment":
        asv = struct.get("Assessment", {}) if isinstance(struct.get("Assessment"), dict) else {}
        for p in (asv.get("pillars", {}) or {}).keys():
            i += 1
            triples.append({"id": make_id(i), "subject": {"name": p, "type": "Pillar"}, "predicate": "is_a", "object": {"name": "Pillar", "type": "Class"}, "tags": ["Assessment"], "confidence": (default_conf if default_conf is not None else 0.80)})
        for cr in asv.get("criteria", []) or []:
            i += 1
            triples.append({"id": make_id(i), "subject": {"name": cr, "type": "Criterion"}, "predicate": "belongs_to", "object": {"name": "Assessment", "type": "Artifact"}, "tags": ["Assessment"], "confidence": (default_conf if default_conf is not None else 0.70)})
    elif at == "Diagram":
        dg = struct.get("Diagram", {}) if isinstance(struct.get("Diagram"), dict) else {}
        for e in dg.get("entities", []) or []:
            i += 1
            triples.append({"id": make_id(i), "subject": {"name": e, "type": "Entity"}, "predicate": "appears_in", "object": {"name": "Diagram", "type": "Artifact"}, "tags": ["Diagram"], "confidence": (default_conf if default_conf is not None else 0.70)})
    return triples


def main():
    ap = argparse.ArgumentParser(description="Analyze detected regions with LLM and write artifacts (PVStack + weight policy)")
    ap.add_argument("--detected-dir", default="out/visual/regions_detect", help="Directory with <unit>/regions/region-*.json (pages or generic names)")
    ap.add_argument("--pages", nargs="*", type=int, help="Numeric pages to process (optional)")
    ap.add_argument("--all", action="store_true", help="Process all subdirectories found under detected-dir")
    ap.add_argument("--outdir", default="out/visual/regions_detect", help="Where to write region artifacts (same tree)")
    ap.add_argument("--chat-model", default="gpt-4o")
    ap.add_argument("--skip-existing", action="store_true", help="Skip a region if region-<n>.struct.json already exists")
    ap.add_argument("--profile", default="auto", choices=["auto", "discover", "growth", "governance"], help="Weighting profile (auto = infer from Tagging/keywords)")
    ap.add_argument("--synonyms", default="config/semantic_synonyms.yaml", help="Path to synonyms YAML for canonicalization and text cues")
    ap.add_argument("--weights", default="config/visual_objects_weights.yaml", help="Path to base weights YAML for 50 visual objects")
    ap.add_argument("--tag-threshold-major", type=float, default=0.70)
    ap.add_argument("--tag-threshold-secondary", type=float, default=0.60)
    ap.add_argument("--tag-threshold-hint", type=float, default=0.55)
    ap.add_argument("--tmpdir", default="", help="If set, ensures this TMPDIR exists and sets os.environ['TMPDIR'] for OCR")
    args = ap.parse_args()

    # Set TMPDIR for OCR if requested
    if args.tmpdir:
        try:
            Path(args.tmpdir).mkdir(parents=True, exist_ok=True)
            os.environ["TMPDIR"] = args.tmpdir
        except Exception:
            pass
    client = openai_client()
    synonyms = _load_synonyms(Path(args.synonyms))
    # Load base weights config
    base_weights: Dict[str, float] = {}
    try:
        if args.weights and yaml is not None and Path(args.weights).exists():
            with open(args.weights, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                for k, v in (data.get("VisualObjectsBaseWeight", {}) or {}).items():
                    try:
                        base_weights[str(k).strip().lower()] = float(v)
                    except Exception:
                        pass
    except Exception:
        base_weights = {}
    root = Path(args.detected_dir)
    if args.all or not args.pages:
        units = [d.name for d in sorted(root.iterdir()) if d.is_dir()]
    else:
        units = [str(p) for p in args.pages]

    for unit in units:
        rdir = root / unit / "regions"
        files = [p for p in sorted(rdir.glob("region-*.json")) if not p.name.endswith(".struct.json")]
        count = 0
        for jf in files:
            reg = json.loads(jf.read_text())
            try:
                rid = int(jf.stem.split("-")[-1])
            except Exception:
                continue
            # OCR handling for s3 (text signal)
            def _merge_text(a: str, b: str) -> str:
                a = (a or "").strip()
                b = (b or "").strip()
                if not a:
                    return b
                if not b:
                    return a
                if b.lower() in a.lower():
                    return a
                if a.lower() in b.lower():
                    return b
                return (a + "\n" + b)

            reg_text = reg.get("text", "") or ""
            phrase = str(((reg.get("gdino") or {}).get("phrase") or "")).lower()
            needs_ocr = (len(reg_text) < 24) or ("textbox" in phrase) or ("table" in phrase)
            if reg.get("image_b64") and needs_ocr:
                ocr = ocr_from_b64(reg.get("image_b64") or "")
                if ocr:
                    reg_text = _merge_text(reg_text, ocr)
            if args.skip_existing:
                struct_path = rdir / f"region-{rid}.struct.json"
                if struct_path.exists() and struct_path.stat().st_size > 0:
                    # Skip re-analysis to save tokens/time
                    continue
            caption, struct = llm_analyze(client, reg_text, reg.get("image_b64") or "", args.chat_model)
            # Canonicalize PVStack layers
            if isinstance(struct.get("Canvas"), dict) and isinstance(struct["Canvas"].get("layers"), list):
                struct["Canvas"]["layers"] = canonicalize_layers(struct["Canvas"].get("layers") or [], synonyms)
            # Determine profile
            profile = args.profile if args.profile != "auto" else choose_profile(struct, reg_text)
            w1, w2, w3, w4 = profile_weights(profile)
            # Signals
            s1 = float((reg.get("gdino") or {}).get("conf") or 0.5)
            # s2: mask-quality signal (if available later). Fallback neutral 0.5
            s2 = 0.5
            s3 = score_text(reg_text, synonyms)
            s4 = score_layout(reg.get("layout") or {})
            # Confidence
            confidence_visual = max(0.0, min(1.0, (s1 * w1) + (s2 * w2) + (s3 * w3) + (s4 * w4)))
            # Base weight from VisualObject, fallback 0.6
            tagging = struct.get("Tagging") if isinstance(struct.get("Tagging"), dict) else {}
            # Base weight
            def bw_lookup(name: str) -> float:
                key = (name or "").strip().lower()
                return base_weights.get(key, base_weight_for_visual_object(key))
            base_w = bw_lookup((tagging or {}).get("VisualObject") or "")
            # Context bonuses
            ctx_bonus = 0.0
            sust = (tagging or {}).get("Sustainability") or {}
            try:
                if any(bool(sust.get(k)) for k in ("People", "Planet", "Profit")) or (sust.get("SDG") or []):
                    ctx_bonus += 0.10
            except Exception:
                pass
            if tagging and tagging.get("Role"):
                ctx_bonus += 0.02
            if tagging and tagging.get("Zone"):
                ctx_bonus += 0.02
            # s2 from mask_stats if available
            ms = (reg.get("mask_stats") or {}) if isinstance(reg.get("mask_stats"), dict) else {}
            try:
                s2 = float(ms.get("s2", s2))  # type: ignore[name-defined]
            except Exception:
                pass
            # Penalty for poor contour+no text
            poor_contour = True if (ms and s2 < 0.35) else False
            if poor_contour and s3 < 0.2:
                ctx_bonus -= 0.20
            final_weight = base_w * confidence_visual * (1.0 + ctx_bonus)
            final_weight = max(0.0, min(1.0, final_weight))
            # Attach scoring into struct for traceability
            struct.setdefault("Scoring", {})
            struct["Scoring"].update(
                {
                    "profile": profile,
                    "signals": {"s1_dino": s1, "s2_sam2": s2, "s3_text": s3, "s4_layout": s4},
                    "weights": {"w1": w1, "w2": w2, "w3": w3, "w4": w4},
                    "confidence_visual": confidence_visual,
                    "base_weight": base_w,
                    "context_bonus": ctx_bonus,
                    "final_weight": final_weight,
                    "thresholds": {
                        "major": args.tag_threshold_major,
                        "secondary": args.tag_threshold_secondary,
                        "hint": args.tag_threshold_hint,
                    },
                }
            )
            # Auto-tagging tier
            tier = "None"
            if final_weight >= args.tag_threshold_major:
                tier = "Major"
            elif final_weight >= args.tag_threshold_secondary:
                tier = "Secondary"
            elif final_weight >= args.tag_threshold_hint:
                tier = "Hint"
            # Save into Tagging
            if isinstance(tagging, dict):
                tagging["AutoTier"] = tier
                tagging["AutoScore"] = round(final_weight, 4)
                struct["Tagging"] = tagging
            # save artifacts
            out_rdir = Path(args.outdir) / unit / "regions"
            out_rdir.mkdir(parents=True, exist_ok=True)
            (out_rdir / f"region-{rid}.caption.txt").write_text(caption + "\n", encoding="utf-8")
            (out_rdir / f"region-{rid}.struct.json").write_text(json.dumps(struct, ensure_ascii=False, indent=2))
            # ensure png exists
            png_path = out_rdir / f"region-{rid}.png"
            if reg.get("image_b64"):
                try:
                    png_path.write_bytes(base64.b64decode(reg["image_b64"]))
                except Exception:
                    pass
            if not png_path.exists():
                ensure_png(png_path, caption, reg.get("text", ""))
            # facts
            try:
                page_int = int(unit)
            except Exception:
                page_int = -1
            triples = synthesize_triples(struct, page=page_int, rid=rid, default_conf=struct.get("Scoring", {}).get("final_weight"))
            if triples:
                with open(out_rdir / f"region-{rid}.facts.jsonl", "w", encoding="utf-8") as f:
                    for tr in triples:
                        tr["provenance"] = {"page": page_int if page_int >= 0 else None, "region_id": rid, "bbox": reg.get("bbox"), "snippet": (reg.get("text") or "")[:240]}
                        f.write(json.dumps(tr, ensure_ascii=False) + "\n")
            count += 1
        print(f"Analyzed {count} detected regions in unit {unit} -> {rdir}")


if __name__ == "__main__":
    main()
