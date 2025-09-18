#!/usr/bin/env python3
import os
import sys
import json
import platform
import subprocess as sp
import socket
from pathlib import Path


def cmd(s: str, timeout: int = 10):
    try:
        p = sp.run(
            s,
            shell=True,
            stdout=sp.PIPE,
            stderr=sp.STDOUT,
            text=True,
            timeout=timeout,
        )
        return p.stdout.strip() if p.returncode == 0 and p.stdout else None
    except Exception:
        return None


def read_os_release():
    p = Path('/etc/os-release')
    out = {}
    if p.exists():
        for line in p.read_text().splitlines():
            if '=' in line:
                k, v = line.split('=', 1)
                out[k] = v.strip().strip('"')
    return out


def main():
    env_keep = ['OPENAI', 'HF_', 'TRANSFORMERS', 'TORCH', 'CUDA', 'MODEL', 'DATA', 'INDEX', 'PDF']

    data = {
        'host': {
            'hostname': socket.gethostname(),
            'user': os.getenv('USER') or os.getenv('USERNAME'),
            'cwd': os.getcwd(),
        },
        'network': {
            'fqdn': socket.getfqdn(),
            'interfaces_json': cmd('ip -j addr 2>/dev/null | head -c 12000') or cmd('ip addr | sed -n "1,200p"'),
            'routing': cmd('ip route | sed -n "1,60p"'),
            'dns': (lambda: (lambda p: (
                {'nameservers': [l.split()[1] for l in p if l.startswith('nameserver')],
                 'search': next((l.split(None,1)[1] for l in p if l.startswith('search')), None),
                 'raw': '\n'.join(p) }
            ))(open('/etc/resolv.conf','r',encoding='utf-8',errors='ignore').read().splitlines()) if os.path.exists('/etc/resolv.conf') else None)(),
            'open_ports': cmd('ss -tulpen 2>/dev/null | sed -n "1,60p"') or cmd('netstat -tulpen 2>/dev/null | sed -n "1,60p"'),
            'firewall': cmd('ufw status 2>/dev/null | sed -n "1,80p"') or cmd('iptables -S 2>/dev/null | sed -n "1,80p"') or cmd('nft list ruleset 2>/dev/null | sed -n "1,40p"'),
            'proxies': {k: os.getenv(k) for k in ['HTTP_PROXY','HTTPS_PROXY','NO_PROXY','http_proxy','https_proxy','no_proxy'] if os.getenv(k)},
            'connectivity': {
                'example.com': cmd("curl -sS -m 3 -o /dev/null -w '%{http_code}' https://example.com") or cmd('ping -c 1 -W 1 example.com 2>/dev/null | head -n 2'),
                'github.com': cmd("curl -sS -m 3 -o /dev/null -w '%{http_code}' https://github.com") or cmd('ping -c 1 -W 1 github.com 2>/dev/null | head -n 2'),
                'api.openai.com': cmd("curl -sS -m 3 -o /dev/null -w '%{http_code}' https://api.openai.com/v1") or cmd('ping -c 1 -W 1 api.openai.com 2>/dev/null | head -n 2'),
            }
        },
        'os': {
            'uname': cmd('uname -a'),
            'os_release': read_os_release(),
            'cpu': cmd("lscpu | sed -n '1,12p'"),
            'mem': cmd('free -h'),
            'disk': cmd("df -h -x tmpfs -x devtmpfs | sed -n '1,8p'"),
        },
        'gpu_cuda': {
            'nvidia_smi': cmd("nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader || nvidia-smi -L"),
            'nvcc': cmd('nvcc --version | sed -n "1,3p"'),
            'CUDA_VISIBLE_DEVICES': os.getenv('CUDA_VISIBLE_DEVICES'),
        },
        'python': {
            'executable': sys.executable,
            'version': sys.version.splitlines()[0],
            'pip': cmd(f"{sys.executable} -m pip --version"),
            'top_packages': cmd(f"{sys.executable} -m pip list --format=freeze | head -n 40") or cmd(f"{sys.executable} -m pip list | head -n 40"),
            'venv': os.getenv('VIRTUAL_ENV'),
            'conda_prefix': os.getenv('CONDA_PREFIX'),
            'conda_info': cmd('conda info --json | head -c 5000') or cmd('conda info | sed -n "1,60p"'),
        },
        'jupyter': {
            'version': cmd('jupyter --version'),
            'kernels': cmd('jupyter kernelspec list --json | head -c 4000') or cmd('jupyter kernelspec list'),
        },
        'git': {
            'root': cmd('git rev-parse --show-toplevel') or os.getcwd(),
            'branch': cmd('git rev-parse --abbrev-ref HEAD'),
            'remotes': cmd('git remote -v'),
            'submodules': cmd('git submodule status'),
            'status_short': cmd('git status -s -b | head -n 20'),
        },
        'env_vars': {k: v for k, v in os.environ.items() if any(k.startswith(p) for p in env_keep)},
        'paths_guess': {
            'out_exists': str(Path('out').resolve()) if Path('out').exists() else None,
            'data_dir': os.getenv('DATA_DIR') or (str(Path('data').resolve()) if Path('data').exists() else None),
            'models_dir': os.getenv('MODEL_DIR'),
        },
        'repo_hints': {
            'out_tree': cmd('ls -R out 2>/dev/null | sed -n "1,100p"'),
        },
    }

    save_path = None
    try:
        repo_root = data['git']['root'] or os.getcwd()
        out_dir = Path(repo_root) / 'docs' / 'infra'
        out_dir.mkdir(parents=True, exist_ok=True)
        save_path = out_dir / f"machine-{data['host']['hostname']}.json"
        save_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f'WARN: cannot write file in repo: {e}', file=sys.stderr)

    print('---BEGIN JSON---')
    print(json.dumps(data, ensure_ascii=False, indent=2))
    print('---END JSON---')
    if save_path:
        print(f'Wrote to {save_path}')


if __name__ == '__main__':
    main()
