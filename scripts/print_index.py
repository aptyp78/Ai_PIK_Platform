import json
from pathlib import Path
items=[]
with open('out/openai_embeddings.ndjson','r') as f:
    for line in f:
        if line.strip(): items.append(json.loads(line))
for it in items:
    m=it.get('meta',{})
    t=it.get('text','')
    print(f"ID={it['id']} page={m.get('page')} type={m.get('type')} span={m.get('span')}")
    print(t)
    print('---')
