# Main Machine Profile

This file summarizes the current main machine configuration. It can be regenerated from the latest snapshot using `scripts/generate_machine_docs.py` after running `scripts/system_probe.py`.

Overview
- Hostname: af4e8805195b
- OS: Ubuntu 22.04 (jammy)
- CPU: 11th Gen Intel(R) Core(TM) i5-11600KF @ 3.90GHz (12 threads)
- Memory: ~62GiB
- GPU: NVIDIA GeForce RTX 4090, driver 575.64.03
- CUDA: nvcc present (2023 build)
- Python: 3.11.9 (conda base at /opt/conda)
- Repo root: /root/AiPIK

Key Paths
- Working directory: /root/AiPIK
- Outputs: out/
  - out/page_images/PIK - Expert Guide - Platform IT Architecture - Playbook - v11
  - out/visual/cv_regions
  - out/visual/grounded_regions

Environment Variables
- OPENAI_API_KEY required for LLM operations
- See `.env.example` for other commonly used variables (MODEL_DIR, DATA_DIR, PDF_PATH, JSON_PATH, OUT_PAGES, OUT_DET, INDEX_PATH, CHAT_MODEL, EMB_MODEL, USE_CV)

## Network
This section is populated by scripts/generate_machine_docs.py from the latest machine snapshot.

- FQDN: (autogen)
- Default route: (autogen)
- DNS / Proxies: (autogen)
- Connectivity checks: (autogen)

How to Run
1) Optional: activate conda base
   - source /opt/conda/etc/profile.d/conda.sh && conda activate base
2) Load env variables from `.env`
   - bash: set -a; [ -f .env ] && source .env; set +a
3) Execute notebook headless
   - jupyter nbconvert --to notebook --execute --inplace notebooks/Grounded_DINO_SAM2_Detection_v2.ipynb

Maintenance
- Regenerate machine snapshot: `python3 scripts/system_probe.py` (writes JSON under `docs/infra/`)
- Keep `.env` uncommitted; commit only `.env.example` with placeholders.
