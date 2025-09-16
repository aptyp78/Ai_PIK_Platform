#!/usr/bin/env python3
import json
from pathlib import Path

NB = Path('notebooks/Grounded_DINO_SAM2_Detection.ipynb')

def main():
    nb = json.loads(NB.read_text())
    changed = False
    for cell in nb.get('cells', []):
        if cell.get('cell_type') != 'code':
            continue
        src = cell.get('source') or []
        i = 0
        while i < len(src):
            line = src[i]
            # Detect broken split across two source entries:
            # "... + '\n" followed by a next line that is "')"
            if 'json.dumps(rec' in line and "+ '" in line and i + 1 < len(src) and src[i+1].strip() == "')":
                j = line.rfind("+ '")
                prefix = line[:j]
                src[i] = prefix + "+ '\\n')\n"
                del src[i+1]
                changed = True
                continue
            # Fallback: if the jsonl write has '+ ' and no closing ) on same line
            if 'json.dumps(rec' in line and "+ '" in line and "')" not in line:
                j = line.rfind("+ '")
                prefix = line[:j]
                src[i] = prefix + "+ '\\n')\n"
                changed = True
            # Fix accidental replacement to empty string literal
            if 'json.dumps(rec' in line and "+ '')" in line:
                src[i] = line.replace("+ '')", "+ '\\n')")
            i += 1
        cell['source'] = src
    if changed:
        NB.write_text(json.dumps(nb, ensure_ascii=False, indent=1))
        print('Patched notebook write line (added closing ")")')
    else:
        print('No changes needed')

if __name__ == '__main__':
    main()
