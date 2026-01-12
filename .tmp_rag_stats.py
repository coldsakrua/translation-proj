import json
from pathlib import Path

p = Path('d:/hw/translation-proj/try/output/rag_backups/rag_backup_20260112210224.json')
with open(p,'r',encoding='utf-8') as f:
    data = json.load(f)
print('records:', len(data))
keys=set()
for d in data[:50]:
    keys.update(d.keys())
print('sample_keys:', sorted(keys)[:30])
hr = sum(1 for d in data if d.get('human_reviewed') is True)
hm = sum(1 for d in data if d.get('human_modified') is True)
print('human_reviewed_true:', hr)
print('human_modified_true:', hm)
# detect duplicates by en field
seen=set(); dup=0
for d in data:
    en = (d.get('en') or '').strip()
    if not en:
        continue
    if en in seen:
        dup += 1
    else:
        seen.add(en)
print('duplicate_en_count:', dup)
print('unique_en_count:', len(seen))
