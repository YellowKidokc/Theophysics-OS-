from __future__ import annotations
import argparse
from pathlib import Path
from engines.pipeline.knowledge_graph import KnowledgeGraph

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--sidecar-dir',default=None); ap.add_argument('--out',default='knowledge_graph.json')
    a=ap.parse_args()
    side=Path(a.sidecar_dir or Path(__file__).resolve().parents[1]/'output')
    kg=KnowledgeGraph(); kg.build_from_sidecars(side); kg.export_graph_json(Path(a.out))
    print(kg.coverage_report())
