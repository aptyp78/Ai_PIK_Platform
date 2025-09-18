# Main Machine Profile

This profile is generated from `/root/AiPIK/docs/infra/machine-af4e8805195b.json`.

Overview
- Hostname: af4e8805195b
- OS: Ubuntu 22.04.3 LTS
- CPU/RAM: 32-bit, 64-bit / Mem:            62Gi       3.4Gi       7.9Gi       1.0Mi        51Gi        58Gi
- GPU: NVIDIA GeForce RTX 4090, 575.64.03, 24564 MiB
- Python: 3.11.9 (main, Apr 19 2024, 16:48:06) [GCC 11.2.0] (/opt/conda/bin/python3)

## Network
- FQDN: af4e8805195b
- Default route: via 172.17.0.1 dev eth0
- Primary IPs: 172.17.0.2 (inet)
- DNS: 1.1.1.1, 8.8.8.8; search: lan
- Connectivity checks:
  - example.com: 200
  - github.com: 200
  - api.openai.com: 404

Open ports (preview)

```
Netid State  Recv-Q Send-Q Local Address:Port  Peer Address:PortProcess                                                                                     
tcp   LISTEN 0      100        127.0.0.1:55169      0.0.0.0:*    users:(("python",pid=4197,fd=11)) ino:17165808 sk:4 cgroup:unreachable:8560 <->            
tcp   LISTEN 0      100        127.0.0.1:54091      0.0.0.0:*    users:(("python",pid=4197,fd=9)) ino:17165806 sk:5 cgroup:unreachable:8560 <->             
tcp   LISTEN 0      100        127.0.0.1:60529      0.0.0.0:*    users:(("python",pid=4197,fd=13)) ino:17165810 sk:6 cgroup:unreachable:8560 <->            
tcp   LISTEN 0      511        127.0.0.1:4278       0.0.0.0:*    users:(("node",pid=45610,fd=31)) ino:19196698 sk:1001 cgroup:unreachable:8560 <->          
tcp   LISTEN 0      100        127.0.0.1:37785      0.0.0.0:*    users:(("python",pid=4197,fd=27)) ino:17165818 sk:7 cgroup:unreachable:8560 <->            
tcp   LISTEN 0      100        127.0.0.1:33423      0.0.0.0:*    users:(("python",pid=4197,fd=35)) ino:17169710 sk:8 cgroup:unreachable:8560 <->            
tcp   LISTEN 0      128          0.0.0.0:22         0.0.0.0:*    users:(("sshd",pid=369,fd=4)) ino:17048120 sk:1 cgroup:unreachable:8560 <->                
tcp   LISTEN 0      128        127.0.0.1:8888       0.0.0.0:*    users:(("jupyter-lab",pid=2686,fd=6)) ino:17073017 sk:2 cgroup:unreachable:8560 <->        
tcp   LISTEN 0      100        127.0.0.1:44401      0.0.0.0:*    users:(("python",pid=4197,fd=22)) ino:17165814 sk:b cgroup:unreachable:8560 <->            
```

