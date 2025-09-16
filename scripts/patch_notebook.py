#!/usr/bin/env python3
import json
from pathlib import Path
import re
import subprocess
import sys

NB_PATH = Path('notebooks/Grounded_DINO_SAM2_Detection.ipynb')

def make_code_cell(src: str):
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": src.splitlines(True),
    }

def _load_notebook_or_die(path: Path):
    txt = path.read_text(encoding='utf-8')
    # Detect git conflict markers early — they break JSON parser
    for marker in ('\n<<<<<<< ', '\n=======\n', '\n>>>>>>> '):
        if marker in txt:
            print(f"[error] Notebook has unresolved merge conflict markers: '{marker.strip()}' found in {path}", file=sys.stderr)
            print("[hint] Resolve conflicts: keep notebook from the intended branch (e.g., colab-latest) and re-run.", file=sys.stderr)
            sys.exit(2)
    try:
        return json.loads(txt)
    except json.JSONDecodeError as e:
        print(f"[error] Failed to parse notebook JSON at {path}: {e}", file=sys.stderr)
        print("[hint] The file might be partially merged or corrupted. Resolve conflicts and ensure valid .ipynb.", file=sys.stderr)
        sys.exit(2)


def main():
    nb = _load_notebook_or_die(NB_PATH)
    cells = nb.get('cells', [])

    control_src = '''#@title Run Control and Parameters (disabled gate: runs full volume)
# SIGPIPE-friendly stdout (avoid BrokenPipeError in Colab pipes)
import signal
if hasattr(signal, 'SIGPIPE'):
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)

# Toggle to start the pipeline
START_RUN = True  # gate disabled: always start

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

# Helper to gate execution in subsequent cells (no-op)
def require_start():
    return None

print('Configured. START_RUN=', START_RUN)
print('PDF:', PLAYBOOK_PDF)
print('PAGES (empty=ALL):', PAGES)
print('Frames:', FRAME_NAMES)
print('Prompts:', PROMPTS)
'''

    # Remove any existing Control and Parameters cell; do NOT insert it back
    cells = [c for c in cells if not (c.get('cell_type')=='code' and ''.join(c.get('source') or []).startswith('#@title Run Control and Parameters'))]

    # Insert Cell Execution Logger near top (after first cell)
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
        cells.insert(1 if len(cells)>1 else 0, make_code_cell(logger_src))

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

    # Ensure a no-op require_start exists (remove gating)
    if not any(c.get('cell_type')=='code' and 'def require_start()' in ''.join(c.get('source') or []) for c in cells):
        cells.insert(1, make_code_cell('#@title No-op gate helper\ndef require_start():\n  return None\n'))
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
            curated = '''#@title Install Torch + SAM/SAM2 + GroundedDINO (CUDA-aware)
require_start()

# 1) Update base tooling
!pip -q install --upgrade pip setuptools wheel
!pip -q install -U jedi>=0.16 typing_extensions>=4.14.0 filelock>=3.15

# 2) Torch for detected CUDA (12.4 or 12.1); fallback to CPU
import subprocess, re
def _probe_cuda_tag():
    try:
        out = subprocess.check_output(['bash','-lc','nvcc --version || cat /usr/local/cuda/version.json || true'], text=True)
        m = re.search(r'release (\d+)\.(\d+)', out) or re.search(r'"cuda":\s*"(\d+)\.(\d+)"', out)
        if m:
            major, minor = m.groups()
            ver = f"{major}.{minor}"
        else:
            ver = None
    except Exception:
        ver = None
    if ver and ver.startswith('12.4'):
        return 'cu124'
    if ver and ver.startswith('12.1'):
        return 'cu121'
    # Default to cu121 in Colab
    return 'cu121'

_tag = _probe_cuda_tag()
print('[torch] installing for', _tag)
try:
    get_ipython().system("pip -q install --upgrade --force-reinstall torch==2.5.1 torchvision==0.20.1 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/%s" % _tag)
except Exception as e:
    print('[warn] Torch install failed for', _tag, 'falling back to CPU:', e)
    get_ipython().system("pip -q install --upgrade --force-reinstall torch==2.5.1 torchvision==0.20.1 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cpu")

# 3) Core deps
!pip -q install 'numpy<2.1,>=1.24'
!pip -q install shapely timm opencv-python pycocotools addict yacs requests pillow huggingface_hub

# 4) SAM and SAM2
!pip -q install git+https://github.com/facebookresearch/segment-anything.git
!pip -q install git+https://github.com/facebookresearch/segment-anything-2.git

# 5) GroundingDINO — pip first, fallback to source build
import sys, os, subprocess, importlib

print('[GroundingDINO] installing via pip…')
!pip -q install "git+https://github.com/IDEA-Research/GroundingDINO.git"

try:
    importlib.import_module('groundingdino')
    print('✅ GroundingDINO pip import OK')
except ImportError:
    print('⚠️ pip install failed, building from source…')
    if '/content/GroundingDINO' not in sys.path:
        sys.path.append('/content/GroundingDINO')
    !rm -rf /content/GroundingDINO
    !git clone --depth 1 https://github.com/IDEA-Research/GroundingDINO.git /content/GroundingDINO
    # Build C++ extensions
    try:
        subprocess.check_call(['bash','-lc','sudo apt-get -q update && sudo apt-get -q install -y ninja-build'])
    except Exception as e:
        print('[warn] apt-get ninja-build failed:', e)
    build_dir = '/content/GroundingDINO'
    orig = os.getcwd()
    os.chdir(build_dir)
    try:
        res = subprocess.run([sys.executable, 'setup.py', 'build_ext', '--inplace'], capture_output=True, text=True)
        if res.returncode != 0:
            print('🟥 build_ext failed:\n', res.stderr)
        else:
            print('✅ build_ext ok')
    finally:
        os.chdir(orig)
    try:
        if 'groundingdino' in sys.modules:
            importlib.reload(sys.modules['groundingdino'])
        else:
            importlib.import_module('groundingdino')
        print('✅ GroundingDINO import OK after source build')
    except Exception as e:
        print('🟥 GroundingDINO import still failing:', e)

# 6) Final checks
try:
    import torch, numpy
    print(f"[versions] torch: {torch.__version__}, numpy: {numpy.__version__}")
    from groundingdino.util.inference import Model
    print('✅ GroundingDINO.Model available')
    import segment_anything as _sam
    print('✅ SAM v1 import OK')
    try:
        import sam2 as _sam2
        print('✅ SAM2 import OK')
    except Exception as e:
        print('[warn] SAM2 import failed:', e)
    print('CUDA available:', torch.cuda.is_available())
except Exception as e:
    print('🟥 Final checks failed:', e)

# 7) Harmonize
!pip -q uninstall -y xformers || true
!pip -q install -U 'numpy<2.1,>=1.24' typing_extensions>=4.14.0 filelock>=3.15 gcsfs==2025.3.0 fsspec==2025.3.0
'''
            c['source'] = curated.splitlines(True)
            break

    # Add a "Full Run" helper cell to enumerate all playbooks and frames and render pages
    full_run_title = '#@title Full Run — enumerate playbooks and frames; render all pages'
    if not any(c.get('cell_type')=='code' and ''.join(c.get('source') or []).startswith(full_run_title) for c in cells):
        full_run_src = full_run_title + "\n" + """
require_start()
import os, re, glob, json, subprocess
from pathlib import Path

# Search broadly for sources (avoid sample_data)
SEARCH_ROOTS = ['/content/src_gcs','/content/gcs','/content','/workspace','/home']
IGNORE_DIRS  = {'/content/sample_data'}
OUT_PAGES_DIR = '/content/pages'
MANIFEST      = '/content/full_run_manifest.jsonl'
Path(OUT_PAGES_DIR).mkdir(parents=True, exist_ok=True)

def _gather_playbooks():
  found = []
  for root in SEARCH_ROOTS:
    if not Path(root).exists():
      continue
    for pdf in glob.glob(os.path.join(root, '**', 'playbooks', '*.pdf'), recursive=True):
      if any(pdf.startswith(bad) for bad in IGNORE_DIRS):
        continue
      found.append(pdf)
  # de-dup
  return sorted(set(found))

def _gather_frames():
  found = []
  exts = ('*.png','*.jpg','*.jpeg','*.tif','*.tiff')
  for root in SEARCH_ROOTS:
    if not Path(root).exists():
      continue
    for ext in exts:
      for fp in glob.glob(os.path.join(root, '**', 'frames', '**', ext), recursive=True):
        if any(fp.startswith(bad) for bad in IGNORE_DIRS):
          continue
        found.append(fp)
  return sorted(set(found))

def _pdf_pages(pdf_path: str) -> int:
  try:
    out = subprocess.check_output(['pdfinfo', pdf_path], text=True)
    m = re.search(r'^Pages:\\s+(\\d+)', out, re.M)
    return int(m.group(1)) if m else 0
  except Exception:
    return 0

images = []
pbs = _gather_playbooks()
print('playbooks found:', len(pbs))
for pdf in pbs:
    name = Path(pdf).stem
    out_dir = Path(OUT_PAGES_DIR)/name
    out_dir.mkdir(parents=True, exist_ok=True)
    n = _pdf_pages(pdf)
    print('[render]', name, ': pages=', n)
    for p in range(1, n+1):
      png = out_dir/f'page-{p}.png'
      if not png.exists():
        subprocess.run(['pdftoppm','-f',str(p),'-l',str(p),'-png','-singlefile','-r','150', pdf, str(png.with_suffix(''))], check=True)
      images.append(str(png))

frs = _gather_frames()
print('frames images found:', len(frs))
images.extend(frs)

with open(MANIFEST,'w') as f:
  for im in images:
    f.write(json.dumps({'image': im})+'\n')

print('Prepared images:', len(images))
print('Manifest written to:', MANIFEST)
"""
        cells.append(make_code_cell(full_run_src))

    # Add a batch detection runner that consumes the manifest and writes regions
    batch_title = '#@title Batch Detect — iterate manifest and write regions (+optional GCS upload)'
    if not any(c.get('cell_type')=='code' and ''.join(c.get('source') or []).startswith(batch_title) for c in cells):
        batch_src = batch_title + "\n" + """
require_start()
import os, json, shutil, base64
from pathlib import Path
from PIL import Image

MANIFEST = '/content/full_run_manifest.jsonl'
DETECT_OUT = '/content/grounded_regions'
PROMPTS = ['diagram','canvas','table','legend','arrow','node']
Path(DETECT_OUT).mkdir(parents=True, exist_ok=True)

def _png_b64(img_path: str) -> str:
  try:
    im = Image.open(img_path).convert('RGB')
    import io
    buf = io.BytesIO(); im.save(buf, format='PNG')
    return base64.b64encode(buf.getvalue()).decode('utf-8')
  except Exception:
    return ''

def _fallback_detect(img_path: str, unit_dir: Path):
  (unit_dir/'regions').mkdir(parents=True, exist_ok=True)
  reg = unit_dir/'regions'/'region-1.json'
  b64 = _png_b64(img_path)
  reg.write_text(json.dumps({
    'bbox': {'x':0,'y':0,'w':-1,'h':-1},
    'text': '',
    'image_b64': b64,
  }), encoding='utf-8')
  # copy preview
  try:
    dst = unit_dir/'regions'/'region-1.png'
    if not dst.exists():
      shutil.copy2(img_path, dst)
  except Exception:
    pass

def _unit_from_path(p: Path) -> str:
  # Use parent dir for pages/<doc>/page-<n>.png; else fall back to stem
  if p.parent.name.startswith('page-'):
    return p.parent.parent.name
  if p.parent.name and p.parent.parent.name == 'pages':
    return p.parent.name
  return p.stem

def detect_image(img_path: str):
  # Try to call a notebook-level detect function if present; else fallback placeholder
  nb = globals()
  unit = _unit_from_path(Path(img_path))
  unit_dir = Path(DETECT_OUT)/unit
  fn = nb.get('detect_image_to_regions') or nb.get('run_detection_one')
  if callable(fn):
    try:
      fn(img_path, str(unit_dir))
      return
    except Exception as e:
      print('[warn] detect func failed, fallback:', e)
  _fallback_detect(img_path, unit_dir)

images = []
with open(MANIFEST, 'r', encoding='utf-8') as f:
  for line in f:
    if line.strip():
      obj = json.loads(line)
      images.append(obj.get('image'))

print('Detecting over', len(images), 'images')
for i, im in enumerate(images, start=1):
  try:
    detect_image(im)
    if i % 20 == 0:
      print('..', i, 'done')
  except Exception as e:
    print('[error] failed on', im, e)

print('Local regions root:', DETECT_OUT)

# Optional: upload to GCS if bucket var present
try:
  import subprocess
  bucket = GCS_BUCKET if 'GCS_BUCKET' in globals() else None
  if bucket:
    print('[upload] syncing to', f'gs://{bucket}/grounded_regions')
    subprocess.run(['bash','-lc', f"gsutil -m rsync -r '{DETECT_OUT}' 'gs://{bucket}/grounded_regions'"], check=False)
except Exception as e:
  print('[warn] GCS upload failed:', e)
"""
        cells.append(make_code_cell(batch_src))

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

    # Stamp notebook's own last-change commit (not HEAD) into title and NOTEBOOK_VERSION (and date)
    try:
        sha = subprocess.check_output(
            ['git','log','-n','1','--pretty=format:%h','--', str(NB_PATH)], text=True
        ).strip()
        date_iso = subprocess.check_output(
            ['git','log','-n','1','--pretty=format:%cI','--', str(NB_PATH)], text=True
        ).strip()
    except Exception:
        sha = ''
        date_iso = ''

    if sha:
        # Update top markdown title line `— commit <sha>`
        for c in cells:
            if c.get('cell_type') == 'markdown':
                src = ''.join(c.get('source') or [])
                if 'GroundedDINO + SAM' in src:
                    # replace commit and (optionally) add/update date
                    new = re.sub(r'(— commit )[0-9a-fA-F]{7,}(?: — [^\n]+)?', lambda m: (m.group(1)+sha + (f' — {date_iso}' if date_iso else '')), src)
                    if new == src:
                        # append to first header line
                        lines = src.splitlines(True)
                        if lines and lines[0].lstrip().startswith('#'):
                            if '— commit' in lines[0]:
                                # update hash and add date if missing
                                lines[0] = re.sub(r'(— commit )[^\s]+(?: — [^\n]+)?', f"\\1{sha}" + (f" — {date_iso}" if date_iso else ''), lines[0])
                            else:
                                lines[0] = lines[0].rstrip()+f' — commit {sha}' + (f' — {date_iso}' if date_iso else '') + '\n'
                            new = ''.join(lines)
                    c['source'] = new.splitlines(True)
                    break

        # Update NOTEBOOK_VERSION assignment
        for c in cells:
            if c.get('cell_type') == 'code':
                src = ''.join(c.get('source') or [])
                if 'NOTEBOOK_VERSION' in src:
                    new = re.sub(r"NOTEBOOK_VERSION\s*=\s*['\"]([^'\"]*)['\"]", f"NOTEBOOK_VERSION = '{sha}'", src)
                    if 'NOTEBOOK_UPDATED' in new:
                        new = re.sub(r"NOTEBOOK_UPDATED\s*=\s*['\"]([^'\"]*)['\"]", f"NOTEBOOK_UPDATED = '{date_iso}'", new)
                    else:
                        # append a line for updated date
                        if not new.endswith('\n'):
                            new += '\n'
                        new += f"NOTEBOOK_UPDATED = '{date_iso}'\n"
                    c['source'] = new.splitlines(True)
                    break

        # Update Colab badge links to use a stable branch `colab-latest`
        def _use_colab_branch(txt: str) -> str:
            return re.sub(r"(https://colab\.research\.google\.com/github/[^/]+/[^/]+/blob/)(main|[0-9a-fA-F]{7,})/",
                          r"\1colab-latest/", txt)

        # README.md
        readme = Path('README.md')
        if readme.exists():
            t = readme.read_text(encoding='utf-8')
            tt = _use_colab_branch(t)
            if tt != t:
                readme.write_text(tt, encoding='utf-8')
        # Setup doc
        setup_md = Path('docs/GROUNDED_SAM_SETUP.md')
        if setup_md.exists():
            t = setup_md.read_text(encoding='utf-8')
            tt = _use_colab_branch(t)
            if tt != t:
                setup_md.write_text(tt, encoding='utf-8')
        # Notebook header badge (first markdown cell already loaded in nb)
        for c in cells:
            if c.get('cell_type') == 'markdown':
                src = ''.join(c.get('source') or [])
                if 'colab-badge.svg' in src:
                    new = _use_colab_branch(src)
                    if new != src:
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
