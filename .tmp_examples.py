import json
from pathlib import Path

root = Path('d:/hw/translation-proj')
out = root/'try'/'output'
reports = root/'try'/'reports'

examples = [
  # (paper_human, paper_nohuman, chapter_id, chunk_id)
  ('resnet','resnet_nohuman', 9, 0),
  ('unet','unet_nohuman', 0, 0),
  ('yolo','yolo_nohuman', 14, 1),
]

def load(p):
  with open(p,'r',encoding='utf-8') as f:
    return json.load(f)

def chunk_path(paper, chapter_id, chunk_id):
  return out/paper/f'chapter_{chapter_id}'/f'chunk_{chunk_id:03d}.json'

for human,nohuman,chap,ck in examples:
  hp = chunk_path(human,chap,ck)
  np = chunk_path(nohuman,chap,ck)
  hd = load(hp)
  nd = load(np)
  print('\n===',human,'vs',nohuman,'chapter',chap,'chunk',ck,'===')
  print('source:', (hd.get('source_text') or '')[:300].replace('\n',' '))
  print('nohuman quality:', nd.get('quality_score'),'human quality:', hd.get('quality_score'))
  print('nohuman translation:', (nd.get('translation') or nd.get('combined_translation') or '')[:500].replace('\n',' '))
  print('human translation:', (hd.get('translation') or hd.get('combined_translation') or '')[:500].replace('\n',' '))
