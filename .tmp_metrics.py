import json, glob
from pathlib import Path

root = Path('d:/hw/translation-proj')
reports = root/'try'/'reports'
outputs = root/'try'/'output'

pairs = [
  ('resnet','resnet_nohuman'),
  ('vgg','vgg_nohuman'),
  ('yolo','yolo_nohuman'),
  ('unet','unet_nohuman'),
]

def load(p):
  with open(p,'r',encoding='utf-8') as f:
    return json.load(f)

def find_chunk_file(out_dir, chunk_id):
  pattern = str(outputs/out_dir/'chapter_*'/'chunk_*.json')
  for fp in glob.glob(pattern):
    try:
      d = load(fp)
      if int(d.get('chunk_id',-1)) == int(chunk_id):
        return fp
    except Exception:
      pass
  return None

def get_eval_rows(eval_json):
  if isinstance(eval_json, dict):
    for k in ['chunk_evaluations','evaluations','chunks','results','details']:
      v = eval_json.get(k)
      if isinstance(v, list) and v and isinstance(v[0], dict):
        return v
  if isinstance(eval_json, list):
    return eval_json
  return []

print('### Metric deltas (summary)')
for human, nohuman in pairs:
  h_sum = load(reports/f'{human}_evaluation_metrics_summary.json')
  n_sum = load(reports/f'{nohuman}_evaluation_metrics_summary.json')
  hm = h_sum['metrics_summary']
  nm = n_sum['metrics_summary']
  def avg(m,k):
    return m.get(k,{}).get('average')
  keys = ['quality_score','back_translation','terminology','length_ratio','fluency','number_preservation','bleu','semantic_similarity','edit_distance']
  print(f'\n{human} vs {nohuman}:')
  for k in keys:
    ha, na = avg(hm,k), avg(nm,k)
    if ha is None or na is None:
      continue
    print(f'  {k:20s} {ha:6.2f}  (nohuman {na:6.2f})  delta {ha-na:+.2f}')

print('\n### Candidate chunks with biggest quality_score improvement (from evaluation.json if available)')
for human, nohuman in pairs:
  hp = reports/f'{human}_evaluation.json'
  np = reports/f'{nohuman}_evaluation.json'
  if not hp.exists() or not np.exists():
    print(f'\n{human}: missing evaluation.json pair, skip')
    continue
  h_eval = load(hp)
  n_eval = load(np)
  h_rows = get_eval_rows(h_eval)
  n_rows = get_eval_rows(n_eval)

  def to_map(rows):
    m={}
    for r in rows:
      cid = r.get('chunk_id', r.get('chunk', r.get('id')))
      if cid is None:
        continue
      try:
        m[int(cid)] = r
      except Exception:
        continue
    return m

  hm = to_map(h_rows)
  nm = to_map(n_rows)
  common = sorted(set(hm).intersection(nm))
  if not common:
    print(f'\n{human}: no common chunk ids found in eval json structures')
    continue

  deltas=[]
  for cid in common:
    def q(r):
      if 'quality_score' in r and r['quality_score'] is not None:
        return r['quality_score']
      if isinstance(r.get('metrics'), dict) and r['metrics'].get('quality_score') is not None:
        return r['metrics']['quality_score']
      return None
    hq = q(hm[cid]); nq = q(nm[cid])
    try:
      hq=float(hq); nq=float(nq)
    except Exception:
      continue
    deltas.append((hq-nq, cid, hq, nq))

  deltas.sort(reverse=True)
  print(f'\n{human}: top quality improvements')
  for dq,cid,hq,nq in deltas[:5]:
    hf = find_chunk_file(human, cid)
    nf = find_chunk_file(nohuman, cid)
    print(f'  chunk {cid:3d}: {nq:.2f} -> {hq:.2f} (delta {dq:+.2f})')
    print(f'    nohuman_file={nf}')
    print(f'    human_file  ={hf}')
