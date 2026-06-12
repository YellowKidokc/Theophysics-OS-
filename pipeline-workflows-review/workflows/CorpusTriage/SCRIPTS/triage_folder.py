"""Corpus triage: inventory, dedup, classify, framework tag, rank, report."""
from __future__ import annotations
import argparse, hashlib, json
from collections import defaultdict
from pathlib import Path
from engines.pipeline.station_base import Manifest
from engines.pipeline.stations.classifier import ClassifierStation
from engines.pipeline.stations.framework_classifier import FrameworkClassifierStation

SKIP_EXT={'.png','.jpg','.gif','.pdf','.mp3','.mp4','.wav'}
SKIP_DIR={'__pycache__','.git','node_modules','.obsidian'}

def sha256(fp:Path)->str:
    h=hashlib.sha256(); h.update(fp.read_bytes()); return h.hexdigest()

def triage(source:Path, output:Path)->dict:
    output.mkdir(parents=True,exist_ok=True)
    rows=[]; groups=defaultdict(list)
    cls=ClassifierStation(str(source),str(output/'classified')); fw=FrameworkClassifierStation(str(source),str(output/'framework'))
    for fp in source.rglob('*'):
        if fp.is_dir() or fp.suffix.lower() in SKIP_EXT or any(p in SKIP_DIR for p in fp.parts):
            continue
        h=sha256(fp); groups[h].append(str(fp))
        row={"path":str(fp),"size":fp.stat().st_size,"ext":fp.suffix.lower(),"sha256":h,"modified":fp.stat().st_mtime,"duplicate":False,"quality":0.1}
        if fp.suffix.lower() in {'.md','.txt','.html'}:
            m=Manifest(file_path=str(fp),file_hash=h,pipeline_name='triage',current_station='classifier')
            _,cscore,_=cls.process(fp,m)
            _,fscore,_=fw.process(fp,m)
            words=len(fp.read_text(encoding='utf-8',errors='replace').split())
            row.update({"classifier_score":cscore,"framework_score":fscore,"quality":fscore if words>=200 else 0.2,"doc_type":m.metadata.get('doc_type','unknown'),"laws":m.metadata.get('laws',[])})
        rows.append(row)
    for h,paths in groups.items():
        if len(paths)>1:
            for r in rows:
                if r['sha256']==h: r['duplicate']=True
    ranked=sorted(rows,key=lambda r:r.get('quality',0),reverse=True)
    (output/'triage_manifest.json').write_text(json.dumps(ranked,indent=2),encoding='utf-8')
    (output/'duplicates.json').write_text(json.dumps({h:p for h,p in groups.items() if len(p)>1},indent=2),encoding='utf-8')
    report=f"# Triage Report\n\nTotal files: {len(rows)}\nUnique hashes: {len(groups)}\nDuplicates: {sum(1 for v in groups.values() if len(v)>1)}\n\n## Top 20\n" + "\n".join(f"- {r['path']} ({r.get('quality',0):.2f})" for r in ranked[:20])
    (output/'triage_report.md').write_text(report,encoding='utf-8')
    return {"total":len(rows),"unique":len(groups)}

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--source',required=True); ap.add_argument('--output',required=True)
    a=ap.parse_args(); triage(Path(a.source),Path(a.output))
