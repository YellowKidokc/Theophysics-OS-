from __future__ import annotations
import argparse, json
from pathlib import Path
from engines.pipeline.station_base import Manifest
from engines.pipeline.stations.lossless_formatter import LosslessFormatterStation
from engines.pipeline.stations.vectorizer import VectorizerStation
from engines.pipeline.stations.paper_grader import PaperGraderStation

def run(inp:Path):
    out=inp.parent/'OUTPUT'; out.mkdir(exist_ok=True)
    loss=LosslessFormatterStation(str(inp.parent),str(out/'lossless'))
    vec=VectorizerStation(str(out/'lossless'),str(out/'vectorized'))
    grade=PaperGraderStation(str(out/'vectorized'),str(out/'graded'),queue_dir=str(inp.parent/'_queue'))
    rubric=[]
    for fp in inp.glob('*.md'):
        m=Manifest(file_path=str(fp),file_hash='-',pipeline_name='brain-handoff',current_station='lossless')
        v1=loss.process(fp,m); cleaned=loss.output_dir/f'{fp.stem}.md'
        v2=vec.process(cleaned,m)
        v3=grade.process(cleaned,m)
        rubric.append({"file":fp.name,"lossless":v1[1],"vectorized":v2[1],"grade_status":v3[0].value})
    (out/'session_rubric.json').write_text(json.dumps(rubric,indent=2),encoding='utf-8')
if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--input',required=True)
    run(Path(ap.parse_args().input))
