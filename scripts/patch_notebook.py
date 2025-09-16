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

    # Insert Cell Execution Logger right after control cell
    logger_src = '''#@title Cell Execution Logger
import os, sys, json, time, uuid, warnings
from pathlib import Path
try:
  LOG_DIR  # noqa: F821
except NameError:
  RUN_ID = time.strftime('%Y%m%d-%H%M%S')
  LOCAL_LOG_ROOT = '/content/colab_runs'
  LOG_DIR = Path(LOCAL_LOG_ROOT)/RUN_ID
  LOG_DIR.mkdir(parents=True, exist_ok=True)

from IPython import get_ipython
ip = get_ipython()

class _Tee:
  def __init__(self, stream, buf_list):
    self._s = stream; self._b = buf_list
  def write(self, s):
    try: self._s.write(s)
    finally: self._b.append(s)
  def flush(self):
    try: self._s.flush()
    except Exception: pass

_celllog = {'i': None, 'start': None, 'buf_out':[], 'buf_err':[], 'warns':[], 'id': None}
_orig_out, _orig_err = sys.stdout, sys.stderr
_orig_showwarning = warnings.showwarning
LOG_JSONL = str(LOG_DIR/'cells.jsonl')

def _pre(cell_id):
  _celllog['i'] = ip.execution_count + 1
  _celllog['id'] = str(uuid.uuid4())
  _celllog['start'] = time.time()
  _celllog['buf_out'] = []
  _celllog['buf_err'] = []
  _celllog['warns'] = []
  sys.stdout = _Tee(_orig_out, _celllog['buf_out'])
  sys.stderr = _Tee(_orig_err, _celllog['buf_err'])
  def _sw(message, category, filename, lineno, file=None, line=None):
    _celllog['warns'].append({'message': str(message), 'category': getattr(category,'__name__', str(category)), 'filename': filename, 'lineno': lineno})
    return _orig_showwarning(message, category, filename, lineno, file, line)
  warnings.showwarning = _sw

def _post(result):
  # restore
  sys.stdout = _orig_out
  sys.stderr = _orig_err
  warnings.showwarning = _orig_showwarning
  end = time.time()
  i = _celllog.get('i')
  # Try to get cell source from history
  src = None
  try:
    ih = ip.user_ns.get('_ih', [])
    if i is not None and i < len(ih):
      src = ih[i]
  except Exception:
    src = None
  rec = {
    'cell_id': _celllog.get('id'),
    'execution_count': i,
    'start_ts': _celllog.get('start'),
    'end_ts': end,
    'duration_s': (end - _celllog['start']) if _celllog.get('start') else None,
    'success': bool(getattr(result, 'success', True)),
    'out': ''.join(_celllog.get('buf_out') or []),
    'err': ''.join(_celllog.get('buf_err') or []),
    'warnings': _celllog.get('warns') or [],
    'source': src,
  }
  try:
    with open(LOG_JSONL, 'a', encoding='utf-8') as f:
      f.write(json.dumps(rec, ensure_ascii=False) + '\n')
  except Exception as e:
    print('[cell-logger] write failed:', e)

ip.events.register('pre_run_cell', _pre)
ip.events.register('post_run_cell', _post)
print('[cell-logger] enabled ->', LOG_JSONL)
'''
    if not any(c.get('cell_type')=='code' and ''.join(c.get('source') or []).startswith('#@title Cell Execution Logger') for c in cells):
        cells.insert(2, make_code_cell(logger_src))

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

    # Normalize dependency installation in "Install Torch + ..." cell to avoid resolver conflicts
    for c in cells:
        src = ''.join(c.get('source') or [])
        if src.startswith('#@title Install Torch + SAM/SAM2 + GroundedDINO'):
            body = src
            # 1) Do not upgrade ipython in Colab; ensure jedi/typing_extensions/filelock only
            body = re.sub(r"!pip -q install --upgrade 'ipython[^\n]+\n", "!pip -q install -U jedi>=0.16 typing_extensions>=4.14.0 filelock>=3.15\n", body)
            # 2) Pin numpy to <2.1 to satisfy numba; keep >=1.24
            body = body.replace("!pip -q install 'numpy==2.0.2'\n", "!pip -q install 'numpy<2.1,>=1.24'\n")
            # 3) Ensure Torch 2.5.1 + cu124 set together
            body = re.sub(r"!pip -q install --upgrade --force-reinstall torch==[0-9\.]+ torchvision==[0-9\.]+ torchaudio==[0-9\.]+ --index-url https://download.pytorch.org/whl/[a-z0-9]+\n",
                           "!pip -q install --upgrade --force-reinstall torch==2.5.1 torchvision==0.20.1 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cu124\n",
                           body)
            # 4) Drop xformers strict pin (conflicts with 2.5.1); make optional comment
            body = re.sub(r"!pip -q install xformers[^\n]*\n", "# xformers optional; skipped by default due to wheel/torch version coupling\n", body)
            # 5) Add final compatibility pins to override any downgrades from requirements.txt
            if '# Compatibility pins (final)' not in body:
                body += (
                    "# Compatibility pins (final)\n"
                    "!pip -q uninstall -y xformers || true\n"
                    "!pip -q install -U 'numpy<2.1,>=1.24' typing_extensions>=4.14.0 filelock>=3.15\n"
                    "!pip -q install -U gcsfs==2025.3.0 fsspec==2025.3.0\n"
                    "import importlib, pkgutil;\n"
                    "print('[versions]',\n"
                    "      'torch', __import__('torch').__version__,\n"
                    "      'numpy', __import__('numpy').__version__,\n"
                    "      'typing_extensions', __import__('typing_extensions').__version__,\n"
                    "      'filelock', __import__('filelock').__version__)\n"
                )
            c['source'] = body.splitlines(True)
            break

    # Add explicit cell to upload cell logs to GCS
    upload_src = '''#@title Upload Cell Logs to GCS
require_start()
from pathlib import Path
p = Path(LOG_DIR) / 'cells.jsonl'
if not p.exists():
  print('[log] cells.jsonl not found at', p)
else:
  bucket = GCS_BUCKET if 'GCS_BUCKET' in globals() else 'pik-artifacts-dev'
  prefix = f'colab_runs/{RUN_ID}' if 'RUN_ID' in globals() else 'colab_runs/manual'
  try:
    from google.cloud import storage
    client = storage.Client()
    b = client.bucket(bucket)
    blob = b.blob(f'{prefix}/cells.jsonl')
    blob.content_type = 'application/json'
    blob.upload_from_filename(str(p))
    print('[log] uploaded to', f'gs://{bucket}/{prefix}/cells.jsonl')
  except Exception as e:
    import subprocess
    print('[log] storage client failed, fallback to gsutil:', e)
    cmd = f"gsutil cp '{p}' gs://{bucket}/{prefix}/cells.jsonl"
    subprocess.run(['bash','-lc', cmd], check=False)
'''
    if not any(c.get('cell_type')=='code' and ''.join(c.get('source') or []).startswith('#@title Upload Cell Logs to GCS') for c in cells):
        cells.append(make_code_cell(upload_src))

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
                                lines[0] = re.sub(r'(— commit )[^\s]+', lambda m: m.group(1)+sha, lines[0])
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
