#!/usr/bin/env python3
import argparse
import subprocess
from pathlib import Path
from typing import List, Tuple


def list_pdfs(dir_paths: List[Path]) -> List[Path]:
    items: List[Path] = []
    for d in dir_paths:
        if d.is_file() and d.suffix.lower() == ".pdf":
            items.append(d)
        elif d.is_dir():
            items.extend(sorted(d.rglob("*.pdf")))
    return items


def png_dpi(p: Path) -> Tuple[int, int]:
    try:
        from PIL import Image  # type: ignore
        im = Image.open(p)
        dpi = im.info.get("dpi")
        if isinstance(dpi, tuple) and len(dpi) == 2:
            return int(dpi[0] or 0), int(dpi[1] or 0)
        return 0, 0
    except Exception:
        return 0, 0


def render_pdf(pdf: Path, outdir: Path, dpi: int) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    # Delegate to existing renderer for consistent naming
    # Determine pages via pdfinfo
    try:
        out = subprocess.check_output(["pdfinfo", str(pdf)], text=True)
        total = 0
        for line in out.splitlines():
            if line.lower().startswith("pages:"):
                total = int(line.split(":", 1)[1].strip())
                break
    except Exception:
        total = 0
    pages = list(range(1, total + 1)) if total > 0 else [1]
    cmd = [
        "python",
        "scripts/render_pages.py",
        "--pdf",
        str(pdf),
        "--pages",
        *list(map(str, pages)),
        "--outdir",
        str(outdir),
        "--dpi",
        str(dpi),
    ]
    subprocess.run(cmd, check=True)


def main():
    ap = argparse.ArgumentParser(description="Prepare 300 DPI inputs in out/page_images from playbooks and frames")
    ap.add_argument("--playbooks", default="/root/data/playbooks")
    ap.add_argument("--frames", default="/root/data/frames")
    ap.add_argument("--out-root", default="out/page_images")
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--report", default="eval/inputs_audit.txt")
    args = ap.parse_args()

    playbooks = Path(args.playbooks)
    frames = Path(args.frames)
    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    report = Path(args.report)
    rep_lines: List[str] = []

    # 1) Render all PDFs (playbooks + frames) to 300 dpi
    pdfs = list_pdfs([playbooks, frames])
    for pdf in pdfs:
        outdir = out_root / pdf.stem
        rep_lines.append(f"PDF: {pdf} -> {outdir} (dpi={args.dpi})")
        try:
            render_pdf(pdf, outdir, args.dpi)
        except subprocess.CalledProcessError as e:
            rep_lines.append(f"  [err] render failed: {e}")

    # 2) Audit frames PNGs for low DPI; if corresponding PDF exists we already rendered above
    pngs = list(frames.rglob("*.png")) if frames.exists() else []
    for png in pngs:
        dx, dy = png_dpi(png)
        if dx < args.dpi or dy < args.dpi:
            rep_lines.append(f"PNG low DPI: {png} ({dx}x{dy} dpi)")
            pdf_candidate = png.with_suffix(".pdf")
            if pdf_candidate.exists():
                rep_lines.append(f"  matched PDF exists -> rendered to out/page_images/{pdf_candidate.stem}")
            else:
                # Fallback: copy PNG into out/page_images for downstream usage
                target = out_root / png.stem / "page-1.png"
                target.parent.mkdir(parents=True, exist_ok=True)
                try:
                    target.write_bytes(png.read_bytes())
                    rep_lines.append(f"  copied fallback -> {target}")
                except Exception as e:
                    rep_lines.append(f"  [err] copy failed: {e}")
        else:
            # If good DPI and no PDF, mirror to out so we don't miss it
            pdf_candidate = png.with_suffix(".pdf")
            if not pdf_candidate.exists():
                target = out_root / png.stem / "page-1.png"
                target.parent.mkdir(parents=True, exist_ok=True)
                try:
                    target.write_bytes(png.read_bytes())
                    rep_lines.append(f"PNG good DPI mirrored -> {target}")
                except Exception as e:
                    rep_lines.append(f"  [err] copy failed: {e}")

    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(rep_lines), encoding="utf-8")
    print(f"Wrote report: {report}")


if __name__ == "__main__":
    main()

