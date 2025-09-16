#!/usr/bin/env python3
import json
from pathlib import Path

nb_path = Path('notebooks/Grounded_DINO_SAM2_Detection.ipynb')
nb = json.loads(nb_path.read_text())
changed = False
for cell in nb.get('cells', []):
    if cell.get('cell_type') != 'code':
        continue
    src = cell.get('source') or []
    for i, line in enumerate(src):
        if 'json.dumps(rec' in line and "+ '')" in line:
            src[i] = line.replace("+ '')", "+ '\\n')")
            changed = True
    cell['source'] = src

if changed:
    nb_path.write_text(json.dumps(nb, ensure_ascii=False, indent=1))
    print('Fixed newline literal in logger write line')
else:
    print('No changes needed')

