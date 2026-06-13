"""Ingest crawler output into classifier/framework/vector pipeline."""
from __future__ import annotations
import json, shutil
from pathlib import Path
from engines.pipeline.station_base import Manifest
from engines.pipeline.stations.classifier import ClassifierStation
from engines.pipeline.stations.framework_classifier import FrameworkClassifierStation
from engines.pipeline.stations.vectorizer import VectorizerStation
from engines.pipeline.knowledge_graph import KnowledgeGraph


def ingest_file(json_file: Path, root: Path) -> dict:
    data = json.loads(json_file.read_text(encoding='utf-8'))
    row = data[0] if isinstance(data, list) else data
    md = root / 'OUTPUT' / f"{json_file.stem}.md"
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text(f"# {row.get('title','untitled')}\n\nSource: {row.get('url','')}\n\n{row.get('text','')}", encoding='utf-8')
    m = Manifest(file_path=str(md), file_hash='-', pipeline_name='crawl-ingest', current_station='classifier')
    c = ClassifierStation(str(root/'OUTPUT'), str(root/'OUTPUT'/'classified'))
    fc = FrameworkClassifierStation(str(root/'OUTPUT'/'classified'), str(root/'OUTPUT'/'framework'))
    v = VectorizerStation(str(root/'OUTPUT'/'framework'), str(root/'OUTPUT'/'vectorized'))
    c.process(md, m)
    fc.process(md, m)
    v.process(md, m)
    kg = KnowledgeGraph(); kg.build_from_sidecars(root/'OUTPUT'); kg.export_graph_json(root/'OUTPUT'/'knowledge_graph.json')
    shutil.move(str(json_file), str(root/'ARCHIVE'/json_file.name))
    return {'source': json_file.name, 'url': row.get('url',''), 'authority_score': row.get('authority_score',0)}


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    for d in ['INPUT','OUTPUT','ARCHIVE','LOGS']:
        (root/d).mkdir(parents=True, exist_ok=True)
    report = [ ingest_file(fp, root) for fp in (root/'INPUT').glob('*.json') ]
    (root/'LOGS'/'ingest_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
