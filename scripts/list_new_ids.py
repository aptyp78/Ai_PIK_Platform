import json
idx=[]
with open('out/openai_embeddings.ndjson','r') as f:
    for line in f:
        if line.strip(): idx.append(json.loads(line))
res=[]
for it in idx:
    m=it.get('meta',{})
    fn=(m.get('filename') or '').strip()
    if 'Platform IT Architecture Canvas - Table View' in fn or 'Platform IT Architecture Canvases' in fn or 'Expert Guide - Platform IT Architecture - Assessment - v01' in fn:
        res.append((it['id'], fn, m.get('page'), m.get('type')))
for r in sorted(res):
    print(r)
