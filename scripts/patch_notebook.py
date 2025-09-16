#!/usr/bin/env python3
import json
from pathlib import Path
import re
import subprocess

NB_PATH = Path('notebooks/Grounded_DINO_SAM2_Detection.ipynb')

def make_code_cell(src: str):
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": src.splitlines(True),
    }

def main():
    nb = json.loads(NB_PATH.read_text())
    cells = nb.get('cells', [])

    control_src = '''#@title Run Control and Parameters
# SIGPIPE-friendly stdout (avoid BrokenPipeError in Colab pipes)
import signal
if hasattr(signal, 'SIGPIPE'):
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)

# Toggle to start the pipeline
START_RUN = False  #@param {type:"boolean"}

# Key parameters (leave pages empty to process ALL pages)
PLAYBOOK_PDF = '/content/src_gcs/playbooks/PIK - Expert Guide - Platform IT Architecture - Playbook - v11.pdf'  #@param {type:"string"}
PAGES = []  #@param {type:"raw"}
FRAME_NAMES_INPUT = 'PIK - Platform IT Architecture Canvas - Table View - v01.png, PIK - Platform IT Architecture Canvases - v01.png, PIK - Expert Guide - Platform IT Architecture - Assessment - v01.png'  #@param {type:"string"}
PROMPTS_INPUT = 'diagram,canvas,table,legend,arrow,node'  #@param {type:"string"}
BOX_THRESHOLD = 0.35  #@param {type:"number"}
TEXT_THRESHOLD = 0.25  #@param {type:"number"}
TOPK = 12  #@param {type:"integer"}
DEVICE = 'auto'  #@param ["auto", "cuda", "cpu"]
USE_SAM2 = True  #@param {type:"boolean"}

REPORT_TO_GCS = True  #@param {type:"boolean"}
GCS_BUCKET = 'pik-artifacts-dev'  #@param {type:"string"}
RUN_TAG = ''  #@param {type:"string"}

# Derived lists from string inputs
FRAME_NAMES = [x.strip() for x in FRAME_NAMES_INPUT.split(',') if x.strip()]
PROMPTS = [x.strip() for x in PROMPTS_INPUT.split(',') if x.strip()]
OUT_PAGES_DIR = '/content/pages'
DETECT_OUT = '/content/grounded_regions'

# Helper to gate execution in subsequent cells
def require_start():
    if not START_RUN:
        raise SystemExit('Execution gated. Set START_RUN=True in the top cell and rerun.')

print('Configured. START_RUN=', START_RUN)
print('PDF:', PLAYBOOK_PDF)
print('PAGES (empty=ALL):', PAGES)
print('Frames:', FRAME_NAMES)
print('Prompts:', PROMPTS)
'''

    # Insert control cell at index 1 if not present
    if not any(c.get('cell_type')=='code' and ''.join(c.get('source') or []).startswith('#@title Run Control and Parameters') for c in cells):
        cells.insert(1, make_code_cell(control_src))

    # Replace old Detection Parameters cell with echo-only
    for c in cells:
        src = ''.join(c.get('source') or [])
        if src.startswith('#@title Detection Parameters'):
            echo_src = '''#@title Selected Parameters (echo)
# This cell only echoes current config defined in the top control cell.
try:
    FRAME_NAMES
except NameError:
    FRAME_NAMES = []
try:
    PROMPTS
except NameError:
    PROMPTS = []
print('START_RUN=', START_RUN)
print('PDF:', PLAYBOOK_PDF)
print('PAGES (empty=ALL):', PAGES)
print('Frames:', FRAME_NAMES)
print('Prompts:', PROMPTS)
print('Device:', DEVICE, 'Use SAM2:', USE_SAM2)
print('Report to GCS:', REPORT_TO_GCS, 'Bucket:', GCS_BUCKET, 'Run tag:', RUN_TAG)
'''
            c['source'] = echo_src.splitlines(True)
            break

    # Modify Render Pages cell: add require_start() and empty-pages logic
    for c in cells:
        src = ''.join(c.get('source') or [])
        if src.startswith('#@title Render Pages to PNG'):
            # Insert require_start after title line
            lines = src.splitlines(True)
            if 'require_start()' not in src:
                lines = lines[:1] + ['require_start()\n', '\n'] + lines[1:]
            body = ''.join(lines)
            # Replace loop to use pages_selected
            body = re.sub(r"for p in PAGES:\n\s*print\('Rendering', p\)\n\s*check_call\(\['pdftoppm','-png','-singlefile','-r','150', src, f'{OUT_PAGES_DIR}/page-\{p\}'\]\)\n",
                          "for p in pages_selected:\n  print('Rendering', p)\n  check_call(['pdftoppm','-png','-singlefile','-r','150', src, f'{OUT_PAGES_DIR}/page-{p}'])\n",
                          body)
            # Insert empty-pages expansion logic before the loop
            if 'pages_selected =' not in body:
                extra_logic = (
                    "# If PAGES is empty, compute all pages via pdfinfo\n"
                    "def _detect_all_pages(pdf_path):\n"
                    "    import subprocess, re\n"
                    "    try:\n"
                    "        out = subprocess.check_output(['pdfinfo', pdf_path], text=True)\n"
                    "        m = re.search(r'^Pages:\\\\s+(\\\\d+)', out, re.M|re.I)\n"
                    "        return int(m.group(1)) if m else None\n"
                    "    except Exception:\n"
                    "        return None\n"
                    "pages_selected = list(PAGES) if isinstance(PAGES, list) else []\n"
                    "if not pages_selected:\n"
                    "    n = _detect_all_pages(src)\n"
                    "    if n:\n"
                    "        pages_selected = list(range(1, n+1))\n"
                    "    else:\n"
                    "        raise SystemExit('Cannot determine page count and PAGES is empty')\n"
                    "print('Pages to render:', pages_selected[:20], ('...' if len(pages_selected)>20 else ''))\n\n"
                )
                # Try inserting right after the '# Render pages' marker
                if '\n# Render pages\n' in body:
                    body = body.replace('\n# Render pages\n', '\n# Render pages\n' + extra_logic)
                else:
                    # Fallback: insert immediately before the loop
                    idx = body.find('\nfor p in pages_selected:')
                    if idx != -1:
                        body = body[:idx] + '\n' + extra_logic + body[idx:]
            c['source'] = body.splitlines(True)
            break

    # Add require_start to heavy-action cells
    prefixes = [
        'Боевой режим: GroundedDINO',
        '#@title Upload Regions to GCS',
        '#@title Auth + gcsfuse setup',
        '#@title Mount GCS buckets',
        '#@title Install Torch + SAM/SAM2 + GroundedDINO',
    ]
    for c in cells:
        src = ''.join(c.get('source') or [])
        if any(src.startswith(p) for p in prefixes):
            if 'require_start()' not in src:
                lines = src.splitlines(True)
                lines = lines[:1] + ['require_start()\n', '\n'] + lines[1:]
                c['source'] = lines

    # Stamp current git commit into title and NOTEBOOK_VERSION
    try:
        sha = subprocess.check_output(['git','rev-parse','--short','HEAD'], text=True).strip()
    except Exception:
        sha = ''

    if sha:
        # Update top markdown title line `— commit <sha>`
        for c in cells:
            if c.get('cell_type') == 'markdown':
                src = ''.join(c.get('source') or [])
                if 'GroundedDINO + SAM' in src:
                    # replace if present
                    new = re.sub(r'(— commit )[0-9a-fA-F]{7,}', lambda m: m.group(1)+sha, src)
                    if new == src:
                        # append to first header line
                        lines = src.splitlines(True)
                        if lines and lines[0].lstrip().startswith('#'):
                            if '— commit' in lines[0]:
                                lines[0] = re.sub(r'(— commit )[^\s]+', r'\1'+sha, lines[0])
                            else:
                                lines[0] = lines[0].rstrip()+f' — commit {sha}\n'
                            new = ''.join(lines)
                    c['source'] = new.splitlines(True)
                    break

        # Update NOTEBOOK_VERSION assignment
        for c in cells:
            if c.get('cell_type') == 'code':
                src = ''.join(c.get('source') or [])
                if 'NOTEBOOK_VERSION' in src:
                    new = re.sub(r"NOTEBOOK_VERSION\s*=\s*['\"]([^'\"]*)['\"]", f"NOTEBOOK_VERSION = '{sha}'", src)
                    c['source'] = new.splitlines(True)
                    break

    nb['cells'] = cells
    # Sanitize metadata for GitHub renderer: remove widget state blob
    if isinstance(nb.get('metadata'), dict) and 'widgets' in nb['metadata']:
        try:
            del nb['metadata']['widgets']
        except Exception:
            pass
    NB_PATH.write_text(json.dumps(nb, ensure_ascii=False, indent=1))
    print('Notebook patched successfully.')

if __name__ == '__main__':
    main()
