from __future__ import annotations
import argparse
from pathlib import Path
from engines.pipeline.knowledge_graph import KnowledgeGraph

def brief(topic:str,graph_path:Path)->str:
  kg=KnowledgeGraph()
  if graph_path.exists():
    import json
    data=json.loads(graph_path.read_text())
    for n in data.get('nodes',[]): kg.nodes[n['id']]={k:v for k,v in n.items() if k!='id'}
    for e in data.get('edges',[]): kg.adj[e['source']][e['target']]=e.get('edge_type','relates_to'); kg.adj[e['target']][e['source']]=e.get('edge_type','relates_to')
  related=[n for n in kg.nodes if topic.lower() in n.lower()][:10]
  return f"# Tactical Brief: {topic}\n\n## Strongest objections\n- ...\n\n## Counter-arguments\n- ...\n\n## Relevant nodes\n"+'\n'.join(f'- {r}' for r in related)
if __name__=='__main__':
  ap=argparse.ArgumentParser(); ap.add_argument('--topic',required=True); ap.add_argument('--graph',required=True); ap.add_argument('--out',required=True); a=ap.parse_args()
  Path(a.out).write_text(brief(a.topic,Path(a.graph)),encoding='utf-8')
