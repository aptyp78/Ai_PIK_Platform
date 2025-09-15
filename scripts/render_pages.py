#!/usr/bin/env python3
import argparse
import base64
import subprocess
from pathlib import Path


def render_pdf_pages(pdf: Path, pages: list[int], outdir: Path, dpi: int = 150) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    for p in pages:
        # pdftoppm page range one-by-one to stable naming
        png_path = outdir / f"page-{p}.png"
        # -f p -l p: first/last page; -singlefile ensures one image
        cmd = [
            "pdftoppm",
            "-f",
            str(p),
            "-l",
            str(p),
            "-png",
            "-singlefile",
            "-r",
            str(dpi),
            str(pdf),
            str(png_path.with_suffix("").as_posix()),
        ]
        subprocess.run(cmd, check=True)
        print(f"Rendered {pdf.name} page {p} -> {png_path}")


def main():
    ap = argparse.ArgumentParser(description="Render specific PDF pages to PNG via pdftoppm")
    ap.add_argument("--pdf", required=True, help="Path to source PDF")
    ap.add_argument("--pages", nargs="+", type=int, help="Pages to render (1-based)")
    ap.add_argument("--outdir", default="out/page_images", help="Output directory")
    ap.add_argument("--dpi", type=int, default=150)
    args = ap.parse_args()

    render_pdf_pages(Path(args.pdf), [int(p) for p in args.pages], Path(args.outdir), dpi=args.dpi)


if __name__ == "__main__":
    main()

