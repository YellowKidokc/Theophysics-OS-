from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

def sha(p:Path):
  h=hashlib.sha256(); h.update(p.read_bytes()); return h.hexdigest()
if __name__=='__main__':
  ap=argparse.ArgumentParser(); ap.add_argument('--input',required=True); ap.add_argument('--output',required=True); a=ap.parse_args()
  out=Path(a.output); out.mkdir(parents=True,exist_ok=True); rows=[]; seen={}
  for fp in Path(a.input).rglob('*'):
    if fp.is_dir(): continue
    hs=sha(fp); dup=hs in seen; seen[hs]=str(fp)
    quality=min(1.0,max(0.1,len(fp.name)/30)); bucket='gold' if quality>0.75 else 'framework' if quality>0.5 else 'junk'
    rows.append({'file':str(fp),'sha256':hs,'duplicate':dup,'quality':quality,'bucket':bucket})
  (out/'triage_manifest.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
