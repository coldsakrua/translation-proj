import json
from pathlib import Path

root = Path('d:/hw/translation-proj')
reports = root/'try'/'reports'

def load(p):
    with open(p, 'r', encoding='utf-8') as f:
        return json.load(f)

def chunk_map(report):
    m = {}
    for r in report.get('chunk_details', []):
        key = (int(r['chapter_id']), int(r['chunk_id']))
        m[key] = r
    return m

pairs = [
    ('resnet', 'resnet_nohuman'),
    ('unet', 'unet_nohuman'),
    ('vgg', 'vgg_nohuman'),
    ('yolo', 'yolo_nohuman'),
]

for human, nohuman in pairs:
    h = load(reports / f'{human}_evaluation.json')
    n = load(reports / f'{nohuman}_evaluation.json')
    hm = chunk_map(h)
    nm = chunk_map(n)
    common = sorted(set(hm).intersection(nm))
    deltas = []
    for k in common:
        hq = float(hm[k].get('quality_score', 0))
        nq = float(nm[k].get('quality_score', 0))
        deltas.append((hq - nq, k, hq, nq))

    deltas.sort(reverse=True)
    print('\n', human, 'top +螖 quality_score')
    for dq, k, hq, nq in deltas[:5]:
        print(f'  {k}: {nq:.1f}->{hq:.1f} 螖{dq:+.1f}')

    deltas.sort()
    print(human, 'top -螖 quality_score')
    for dq, k, hq, nq in deltas[:5]:
        print(f'  {k}: {nq:.1f}->{hq:.1f} 螖{dq:+.1f}')
