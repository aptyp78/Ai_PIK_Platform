#!/usr/bin/env python3
import argparse
import mimetypes
import os
from pathlib import Path
from typing import Iterable


def iter_files(root: Path) -> Iterable[Path]:
    for p in root.rglob('*'):
        if p.is_file():
            yield p


def guess_type(p: Path) -> str:
    if p.suffix.lower() in {'.jsonl'}:
        return 'application/json'
    if p.suffix.lower() in {'.json'}:
        return 'application/json'
    if p.suffix.lower() in {'.txt', '.md', '.csv'}:
        return 'text/plain; charset=utf-8'
    if p.suffix.lower() in {'.png'}:
        return 'image/png'
    if p.suffix.lower() in {'.html'}:
        return 'text/html; charset=utf-8'
    t, _ = mimetypes.guess_type(str(p))
    return t or 'application/octet-stream'


def main():
    ap = argparse.ArgumentParser(description='Upload local artifacts to GCS bucket (mirrors directory to prefix)')
    ap.add_argument('--bucket', required=True, help='GCS bucket name, e.g., pik-artifacts-dev')
    ap.add_argument('--prefix', default='', help='Prefix in bucket, e.g., cv_regions/')
    ap.add_argument('--root', default='out/visual/cv_regions', help='Local root directory to upload')
    ap.add_argument('--dry', action='store_true', help='Dry run (do not upload)')
    args = ap.parse_args()

    try:
        from google.cloud import storage  # type: ignore
    except Exception as e:
        raise SystemExit(f'google-cloud-storage not installed: {e}. Try: pip install google-cloud-storage')

    client = storage.Client()
    bucket = client.bucket(args.bucket)
    root = Path(args.root)
    if not root.exists():
        raise SystemExit(f'Root directory not found: {root}')

    uploaded = 0
    for p in iter_files(root):
        rel = p.relative_to(root)
        blob_name = '/'.join([x for x in [args.prefix.strip('/'), str(rel).replace('\\', '/')] if x])
        blob = bucket.blob(blob_name)
        ctype = guess_type(p)
        if args.dry:
            print(f'[dry] upload {p} -> gs://{args.bucket}/{blob_name} ({ctype})')
            continue
        blob.content_type = ctype
        blob.upload_from_filename(str(p))
        uploaded += 1
        if uploaded % 50 == 0:
            print(f'... uploaded {uploaded} objects')
    print(f'Uploaded {uploaded} files to gs://{args.bucket}/{args.prefix}')


if __name__ == '__main__':
    main()

