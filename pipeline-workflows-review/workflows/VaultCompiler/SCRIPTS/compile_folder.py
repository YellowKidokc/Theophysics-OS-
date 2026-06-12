from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from engines.pipeline.stations.lossless_formatter import LosslessFormatterStation
from engines.pipeline.stations.framework_classifier import FrameworkClassifierStation
from engines.pipeline.knowledge_graph import KnowledgeGraph

def h(p:Path):
    s=hashlib.sha256(); s.update(p.read_bytes()); return s.hexdigest()[:16]

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--source',required=True); ap.add_argument('--output',required=True)
    a=ap.parse_args(); src=Path(a.source); out=Path(a.output); out.mkdir(parents=True,exist_ok=True)
    loss=LosslessFormatterStation(str(src),str(out/'lossless')); fc=FrameworkClassifierStation(str(out/'lossless'),str(out/'framework'))
    report=[]
    for fp in src.rglob('*'):
        if fp.suffix.lower() not in {'.md','.txt'}: continue
        report.append({'file':str(fp),'hash':h(fp)})
        from engines.pipeline.station_base import Manifest
        m=Manifest(file_path=str(fp),file_hash=h(fp),pipeline_name='vault',current_station='lossless')
        loss.process(fp,m); cleaned=loss.output_dir/f"{fp.stem}.md"; fc.process(cleaned,m)
    kg=KnowledgeGraph(); kg.build_from_sidecars(out); kg.export_graph_json(out/'knowledge_graph.json')
    (out/'_COMPILE_REPORT.md').write_text('# Compile Report\n\n'+json.dumps(report,indent=2),encoding='utf-8')
