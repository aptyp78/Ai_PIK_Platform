import json
import sys
ids = set(int(x) for x in sys.argv[1:])
byid={}
with open('out/openai_embeddings.ndjson','r') as f:
    for line in f:
        if line.strip():
            obj=json.loads(line)
            if obj['id'] in ids:
                byid[obj['id']]=obj
for i in sorted(byid):
    m=byid[i]['meta']
    print(f"ID={i} page={m.get('page')} type={m.get('type')} span={m.get('span')}")
    print(byid[i]['text'])
    print('---')
