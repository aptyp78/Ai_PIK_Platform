#!/usr/bin/env python3
import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path


def sha1_file(p: Path) -> str:
    h = hashlib.sha1()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def build_manifest_for_unit(unit_dir: Path) -> dict:
    rdir = unit_dir / "regions"
    if not rdir.exists():
        return {}
    regs = sorted(rdir.glob("region-*.json"))
    captions = sorted(rdir.glob("region-*.caption.txt"))
    structs = sorted(rdir.glob("region-*.struct.json"))
    facts = sorted(rdir.glob("region-*.facts.jsonl"))
    pngs = sorted(rdir.glob("region-*.png"))

    latest_mtime = 0.0
    for p in [*regs, *captions, *structs, *facts, *pngs]:
        try:
            latest_mtime = max(latest_mtime, p.stat().st_mtime)
        except Exception:
            pass
    manifest = {
        "unit": unit_dir.name,
        "counts": {
            "regions": len(regs),
            "captions": len(captions),
            "structs": len(structs),
            "facts_files": len(facts),
            "pngs": len(pngs),
        },
        "hashes": {
            "regions": {p.name: sha1_file(p) for p in regs[:20]},  # cap to 20 for speed
            "structs": {p.name: sha1_file(p) for p in structs[:20]},
        },
        "last_modified": datetime.utcfromtimestamp(latest_mtime).isoformat() + "Z" if latest_mtime else None,
    }
    return manifest


def main():
    ap = argparse.ArgumentParser(description="Write manifest.json under each detected unit directory")
    ap.add_argument("--regions-dir", default="out/visual/grounded_regions")
    args = ap.parse_args()

    root = Path(args.regions_dir)
    if not root.exists():
        raise SystemExit(f"Regions dir not found: {root}")
    units = [d for d in sorted(root.iterdir()) if d.is_dir()]
    total = 0
    for u in units:
        man = build_manifest_for_unit(u)
        if man:
            (u / "manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=2), encoding="utf-8")
            total += 1
    print(f"Wrote manifests for {total} units under {root}")


if __name__ == "__main__":
    main()

