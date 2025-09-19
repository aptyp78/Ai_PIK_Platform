#!/usr/bin/env python3
"""
Batch-render all PDFs from source directories into PNG pages at a fixed DPI.

For each PDF found under --src (recursive), creates output under:
  out/page_images/<pdf_basename>/page-<n>.png

Relies on `pdftoppm` (poppler-utils) and the existing scripts/render_pages.py.
"""
import argparse
import subprocess
from pathlib import Path


def pdf_num_pages(pdf: Path) -> int:
    # Use `pdfinfo` for page count (fast, robust)
    try:
        out = subprocess.check_output(["pdfinfo", str(pdf)], text=True)
        for line in out.splitlines():
            if line.lower().startswith("pages:"):
                return int(line.split(":", 1)[1].strip())
    except Exception as e:
        raise SystemExit(f"Failed to get page count for {pdf}: {e}")
    raise SystemExit(f"Cannot determine page count for {pdf}")


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def main() -> None:
    ap = argparse.ArgumentParser(description="Batch-render PDFs to PNG pages at a given DPI")
    ap.add_argument("--src", nargs="+", default=["/root/data/playbooks", "/root/data/frames"], help="Source directories to scan for PDFs (recursive)")
    ap.add_argument("--out-root", default="out/page_images", help="Output root directory")
    ap.add_argument("--dpi", type=int, default=300, help="DPI for rendering")
    ap.add_argument("--limit", type=int, default=0, help="Limit number of PDFs (0 = all)")
    args = ap.parse_args()

    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    pdfs: list[Path] = []
    for src in args.src:
        p = Path(src)
        if p.is_file() and p.suffix.lower() == ".pdf":
            pdfs.append(p)
        elif p.is_dir():
            pdfs.extend(sorted(p.rglob("*.pdf")))

    if args.limit > 0:
        pdfs = pdfs[: args.limit]

    if not pdfs:
        print("No PDFs found under:", ", ".join(args.src))
        return

    for pdf in pdfs:
        base = pdf.stem
        outdir = out_root / base
        try:
            total = pdf_num_pages(pdf)
        except SystemExit as e:
            print(e)
            continue
        pages = list(range(1, total + 1))
        # Delegate to existing single-file renderer for consistent naming
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
            str(args.dpi),
        ]
        print(f"Rendering {pdf} -> {outdir} (pages: {len(pages)}, dpi={args.dpi})")
        run(cmd)


if __name__ == "__main__":
    main()

