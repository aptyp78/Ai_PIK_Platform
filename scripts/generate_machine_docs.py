#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path


def load_latest_snapshot(root: Path) -> tuple[Path, dict]:
    snap_dir = root / 'docs' / 'infra'
    files = sorted(snap_dir.glob('machine-*.json'), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        raise SystemExit('No machine-*.json snapshot found in docs/infra')
    path = files[0]
    data = json.loads(path.read_text())
    return path, data


def summarize_network(net: dict) -> dict:
    if not net:
        return {}
    routing = net.get('routing') or ''
    default_via = None
    default_dev = None
    for line in routing.splitlines():
        if line.startswith('default '):
            m = re.search(r'default\s+via\s+(\S+)(?:\s+dev\s+(\S+))?', line)
            if m:
                default_via, default_dev = m.group(1), m.group(2)
            break

    # Parse interfaces JSON if available
    addrs = []
    if_json = net.get('interfaces_json')
    if if_json:
        try:
            ifs = json.loads(if_json)
            for it in ifs:
                ifname = it.get('ifname')
                afs = it.get('addr_info') or []
                ips = []
                for ai in afs:
                    local = ai.get('local')
                    fam = ai.get('family')
                    if local and fam in ('inet', 'inet6'):
                        ips.append(f"{local} ({fam})")
                if ips:
                    addrs.append({'ifname': ifname, 'ips': ips})
        except Exception:
            pass

    # Primary interface addresses
    primary_ips = []
    if default_dev and addrs:
        for it in addrs:
            if it['ifname'] == default_dev:
                primary_ips = it['ips']
                break

    dns = net.get('dns') or {}
    nameservers = dns.get('nameservers') or []
    search = dns.get('search')

    proxies = net.get('proxies') or {}
    open_ports = (net.get('open_ports') or '').splitlines()
    firewall = (net.get('firewall') or '').splitlines()
    connectivity = net.get('connectivity') or {}

    return {
        'fqdn': net.get('fqdn'),
        'default_via': default_via,
        'default_dev': default_dev,
        'primary_ips': primary_ips,
        'nameservers': nameservers,
        'search': search,
        'proxies': proxies,
        'open_ports_preview': '\n'.join(open_ports[:10]),
        'firewall_preview': '\n'.join(firewall[:10]),
        'connectivity': connectivity,
    }


def write_main_machine_md(root: Path, snap_path: Path, data: dict, net_sum: dict) -> None:
    host = data.get('host', {})
    os = data.get('os', {})
    gpu = data.get('gpu_cuda', {})
    py = data.get('python', {})
    out = []
    out.append('# Main Machine Profile')
    out.append('')
    out.append(f'This profile is generated from `{snap_path.as_posix()}`.')
    out.append('')
    out.append('Overview')
    out.append(f"- Hostname: {host.get('hostname')}")
    out.append(f"- OS: {os.get('os_release', {}).get('PRETTY_NAME') or os.get('uname')}")
    out.append(f"- CPU/RAM: {os.get('cpu','').splitlines()[1].split(':')[-1].strip() if os.get('cpu') else ''} / {os.get('mem','').splitlines()[1] if os.get('mem') else ''}")
    out.append(f"- GPU: {gpu.get('nvidia_smi')}")
    out.append(f"- Python: {py.get('version')} ({py.get('executable')})")
    out.append('')
    out.append('## Network')
    out.append(f"- FQDN: {net_sum.get('fqdn')}")
    out.append(f"- Default route: via {net_sum.get('default_via')} dev {net_sum.get('default_dev')}")
    ips = net_sum.get('primary_ips') or []
    if ips:
        out.append(f"- Primary IPs: {', '.join(ips)}")
    ns = net_sum.get('nameservers') or []
    if ns:
        out.append(f"- DNS: {', '.join(ns)}" + (f"; search: {net_sum.get('search')}" if net_sum.get('search') else ''))
    proxies = net_sum.get('proxies') or {}
    if proxies:
        out.append(f"- Proxies: " + ', '.join(f"{k}={v}" for k,v in proxies.items()))
    conn = net_sum.get('connectivity') or {}
    if conn:
        out.append("- Connectivity checks:")
        for k, v in conn.items():
            out.append(f"  - {k}: {v}")
    if net_sum.get('open_ports_preview'):
        out.append('')
        out.append('Open ports (preview)')
        out.append('')
        out.append('```')
        out.append(net_sum['open_ports_preview'])
        out.append('```')
    if net_sum.get('firewall_preview'):
        out.append('')
        out.append('Firewall (preview)')
        out.append('')
        out.append('```')
        out.append(net_sum['firewall_preview'])
        out.append('```')
    out.append('')
    (root / 'docs' / 'infra' / 'main-machine.md').write_text('\n'.join(out) + '\n')


def update_agents_md(root: Path, net_sum: dict) -> None:
    path = root / 'AGENTS.md'
    if not path.exists():
        return
    content = path.read_text()
    start = '<!-- BEGIN:AUTOGEN NETWORK -->'
    end = '<!-- END:AUTOGEN NETWORK -->'
    block = []
    block.append(start)
    block.append('Network Summary (autogenerated)')
    block.append(f"- FQDN: {net_sum.get('fqdn')}")
    block.append(f"- Default: via {net_sum.get('default_via')} dev {net_sum.get('default_dev')}")
    ns = net_sum.get('nameservers') or []
    if ns:
        block.append(f"- DNS: {', '.join(ns)}")
    proxies = net_sum.get('proxies') or {}
    if proxies:
        block.append(f"- Proxies: " + ', '.join(f"{k}={v}" for k,v in proxies.items()))
    conn = net_sum.get('connectivity') or {}
    if conn:
        block.append("- Connectivity: " + '; '.join(f"{k}={v}" for k,v in conn.items()))
    block.append(end)
    new_block = '\n'.join(block)

    if start in content and end in content:
        new = re.sub(re.escape(start) + ".*?" + re.escape(end), new_block, content, flags=re.S)
    else:
        new = content.rstrip() + '\n\n' + new_block + '\n'
    path.write_text(new)


def main():
    root = Path(__file__).resolve().parents[1]
    snap_path, data = load_latest_snapshot(root)
    net_sum = summarize_network(data.get('network') or {})
    write_main_machine_md(root, snap_path, data, net_sum)
    update_agents_md(root, net_sum)
    print(f'Updated docs/infra/main-machine.md from {snap_path.name} and injected network summary into AGENTS.md')


if __name__ == '__main__':
    main()

