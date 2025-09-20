#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple


def openai_client():
    from openai import OpenAI
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is required")
    return OpenAI(api_key=api_key)


def _load_synonyms(path: Path) -> Dict[str, Any]:
    try:
        import yaml  # type: ignore
    except Exception:
        yaml = None  # type: ignore
    default: Dict[str, Any] = {
        "PVStack": {
            "Experience": ["Engagement", "User Experience", "UX"],
            "Interactions": ["Ecosystem Connectivity", "Connectivity", "Interaction"],
            "Data": ["Intelligence", "Analytics", "Insights"],
            "Infrastructure": ["Platform Infrastructure", "Infra"],
        },
        "Keywords": [
            "liquidity", "activation", "nfx", "network effects", "pricing", "take rate",
            "value", "jtbd", "roadmap", "ecosystem", "growth", "governance", "risk", "kpi", "data"
        ],
    }
    try:
        if yaml and path.exists():
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            for k in ("PVStack", "Roles", "VisualObjects", "Groups", "Keywords"):
                if k in data and isinstance(data[k], (dict, list)):
                    default[k] = data[k]
    except Exception:
        pass
    return default


def _flatten_lexicon(synonyms: Dict[str, Any]) -> List[str]:
    lex: List[str] = []
    for k in (synonyms.get("Keywords") or []):
        try:
            s = str(k).strip()
            if s:
                lex.append(s)
        except Exception:
            pass
    for sec in ("PVStack", "Roles", "Groups", "VisualObjects"):
        ent = synonyms.get(sec) or {}
        if isinstance(ent, dict):
            for key, alts in ent.items():
                lex.append(str(key))
                for a in (alts or []):
                    lex.append(str(a))
    # dedupe
    seen = set(); out: List[str] = []
    for t in lex:
        tl = t.lower()
        if tl not in seen:
            seen.add(tl); out.append(t)
    return out


def score_text_signal(text: str, synonyms: Dict[str, Any]) -> float:
    if not text:
        return 0.0
    txt = text.lower()
    hits = 0
    for kw in _flatten_lexicon(synonyms):
        if not kw:
            continue
        if re.search(r"\b" + re.escape(kw.lower()) + r"\b", txt):
            hits += 1
            if hits >= 5:
                break
    return max(0.0, min(1.0, hits / 5.0))


def choose_profile(text: str) -> str:
    low = (text or "").lower()
    if re.search(r"\b(growth|scale|scaling|nfx|liquidity|activation|referral)\b", low):
        return "growth"
    if re.search(r"\b(governance|risk|compliance|policy|moderation|ethics|transparency)\b", low):
        return "governance"
    return "discover"


def profile_weights(profile: str) -> Tuple[float, float, float, float]:
    p = (profile or "").strip().lower()
    if p in {"discover", "launch", "discover/launch"}:
        return (0.45, 0.15, 0.30, 0.10)
    if p in {"growth", "scale", "growth/scale"}:
        return (0.55, 0.25, 0.15, 0.05)
    if p in {"governance", "risk", "governance/risks"}:
        return (0.40, 0.20, 0.35, 0.05)
    return (0.45, 0.15, 0.30, 0.10)


def llm_struct_for(client, model: str, caption: str, text: str) -> Dict[str, Any]:
    sys = """You analyze visual regions from platform strategy slides. Extract artifact_type (one of: Canvas, Diagram, Table, Chart, Legend, Node, Arrow, Banner, Text), provide a concise RU caption, and optional Tagging (VisualObject, Role, Zone) if evident. Return JSON only.
    {artifact_type, caption_ru, Tagging?} """
    user = (
        "Текст региона (caption + OCR, если есть):\n" + (caption or "") + "\n\n" + (text or "") +
        "\n\nВерни только JSON."
    )
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": sys}, {"role": "user", "content": user}],
            temperature=0.2,
        )
        content = (resp.choices[0].message.content or "").strip()
        data = json.loads(content)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    # fallback heuristic
    return {"artifact_type": "Text", "caption_ru": (caption or text or "").strip()[:200]}


def process_page(client, model: str, page_dir: Path, synonyms: Dict[str, Any], skip_existing: bool) -> int:
    agg = page_dir / "regions.json"
    if not agg.exists():
        return 0
    try:
        data = json.loads(agg.read_text(encoding="utf-8"))
    except Exception:
        return 0
    regs = data.get("regions") or []
    updated = 0
    r_outdir = page_dir / "regions"
    r_outdir.mkdir(parents=True, exist_ok=True)
    for r in regs:
        rid = int(r.get("rid") or 0)
        if rid <= 0:
            continue
        struct_path = r_outdir / f"region-{rid}.struct.json"
        if skip_existing and struct_path.exists() and struct_path.stat().st_size > 0:
            continue
        caption = (r.get("caption") or "").strip()
        text = (r.get("text") or "").strip()
        struct = llm_struct_for(client, model, caption, text)
        # scoring
        s1 = float(((r.get("gdino") or {}).get("conf") or 0.5))
        s2 = float(((r.get("mask_stats") or {}).get("s2") or 0.5))
        s3 = score_text_signal((caption + "\n" + text).strip(), synonyms)
        s4 = 0.7  # layout neutral-ish; we don't recompute here
        prof = choose_profile(caption + "\n" + text)
        w1, w2, w3, w4 = profile_weights(prof)
        conf_vis = max(0.0, min(1.0, (s1*w1)+(s2*w2)+(s3*w3)+(s4*w4)))
        base_w = 0.6
        final = max(0.0, min(1.0, base_w * conf_vis))
        tier = "Major" if final >= 0.70 else ("Secondary" if final >= 0.55 else ("Hint" if final >= 0.45 else "None"))
        # write struct
        out = dict(struct)
        out.setdefault("Scoring", {})
        out["Scoring"].update({
            "profile": prof,
            "signals": {"s1_dino": s1, "s2_sam2": s2, "s3_text": s3, "s4_layout": s4},
            "confidence_visual": conf_vis,
            "final_weight": final,
        })
        tag = out.get("Tagging") if isinstance(out.get("Tagging"), dict) else {}
        if isinstance(tag, dict):
            tag["AutoTier"] = tier
            tag["AutoScore"] = round(final, 4)
            out["Tagging"] = tag
        struct_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        # also update in regions.json entry (lightweight refs)
        r.setdefault("Tagging", {})
        r["Tagging"]["AutoTier"] = tier
        r["Tagging"]["AutoScore"] = round(final, 4)
        r["struct_type"] = str(out.get("artifact_type") or r.get("struct_type") or "").strip() or r.get("struct_type")
        r.setdefault("scoring", {})
        r["scoring"]["final_weight"] = final
        updated += 1
    # write back aggregated file
    data["regions"] = regs
    try:
        agg.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return updated


def main():
    ap = argparse.ArgumentParser(description="LLM analysis for unified regions layout (out/visual/regions/gdino_sam2)")
    ap.add_argument("--root", default="out/visual/regions/gdino_sam2")
    ap.add_argument("--model", default="gpt-5-mini")
    ap.add_argument("--skip-existing", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="Limit regions analyzed (for tests)")
    args = ap.parse_args()

    client = openai_client()
    synonyms = _load_synonyms(Path("config/semantic_synonyms.yaml"))
    root = Path(args.root)
    total = 0
    updated = 0
    for slug_dir in sorted([p for p in root.iterdir() if p.is_dir()], key=lambda p: p.name):
        for page_dir in sorted([p for p in slug_dir.iterdir() if p.is_dir()]):
            n = process_page(client, args.model, page_dir, synonyms, args.skip_existing)
            total += 1
            updated += n
            print(f"[unified] {slug_dir.name}/{page_dir.name}: +{n} regions")
            if args.limit and updated >= args.limit:
                break
        if args.limit and updated >= args.limit:
            break
    print(f"Analyzed unified pages: {total}; regions updated: {updated}")


if __name__ == "__main__":
    main()
