import json
from pathlib import Path

root = Path('d:/hw/translation-proj')
reports = root/'try'/'reports'
output = root/'try'/'output'

pairs=[('resnet','resnet_nohuman'),('unet','unet_nohuman'),('vgg','vgg_nohuman'),('yolo','yolo_nohuman')]


def load(p):
    with open(p,'r',encoding='utf-8') as f:
        return json.load(f)

def idx(report):
    m={}
    for r in report.get('chunk_details', []):
        key=(int(r['chapter_id']), int(r['chunk_id']))
        m[key]=r
    return m

def get_metric(r, name):
    try:
        return r['evaluation']['metrics'][name]['score']
    except Exception:
        return None

def path_for(paper, chap, ck):
    return output/paper/f'chapter_{chap}'/f'chunk_{ck:03d}.json'

candidates=[]
for human,nohuman in pairs:
    h=load(reports/f'{human}_evaluation.json')
    n=load(reports/f'{nohuman}_evaluation.json')
    hm=idx(h); nm=idx(n)
    for key in set(hm).intersection(nm):
        hr=hm[key]; nr=nm[key]
        hq=float(hr.get('quality_score',0)); nq=float(nr.get('quality_score',0))
        src=hr.get('source_text','')
        if len(src) < 200:
            continue
        dq=hq-nq
        # prefer big improvement and low nohuman terminology score
        nt=get_metric(nr,'terminology')
        ht=get_metric(hr,'terminology')
        if dq >= 1.0:
            candidates.append((dq, human, nohuman, key[0], key[1], nq, hq, nt, ht, len(src)))

candidates.sort(reverse=True)
print('Top candidates (len(source)>=200, 螖quality>=+1):')
for row in candidates[:15]:
    dq,human,nohuman,chap,ck,nq,hq,nt,ht,ls=row
    print(f'{human} ch{chap} ck{ck}: quality {nq:.1f}->{hq:.1f} 螖{dq:+.1f}  term {nt}->{ht}  len {ls}')
    print('  nohuman:', path_for(nohuman,chap,ck))
    print('  human  :', path_for(human,chap,ck))
