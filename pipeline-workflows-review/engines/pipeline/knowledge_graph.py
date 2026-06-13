"""Knowledge graph engine built from pipeline sidecars."""
from __future__ import annotations
import json
from collections import defaultdict, deque
from enum import Enum
from pathlib import Path

class NodeType(Enum): PAPER="paper"; LAW="law"; AXIOM="axiom"; AXIOM_SCHEMA="axiom_schema"; EQUATION="equation"; CONCEPT="concept"; FRUIT="fruit"; PERSON="person"; EXPERIMENT="experiment"; SERIES="series"; SEVEN_Q="seven_q"
class EdgeType(Enum): DEPENDS_ON="depends_on"; SUPPORTS="supports"; EXTENDS="extends"; CONTRADICTS="contradicts"; ILLUSTRATES="illustrates"; RELATES_TO="relates_to"; SUPERSEDES="supersedes"; DERIVES_FROM="derives_from"; SYMMETRIC_WITH="symmetric_with"; MAPS_TO="maps_to"; PART_OF="part_of"

class KnowledgeGraph:
    def __init__(self): self.nodes={}; self.adj=defaultdict(dict)
    def build_from_sidecars(self, sidecar_dir: Path) -> None:
        for fp in sidecar_dir.rglob("*.framework.json"): self.add_paper(fp.stem.replace('.framework',''), json.loads(fp.read_text(encoding='utf-8')))
    def add_paper(self,paper_id:str,framework_data:dict)->None:
        self.nodes[paper_id]={"node_type":NodeType.PAPER.value,"score":framework_data.get("framework_coverage_score",0)}
        for law in framework_data.get("laws_referenced",[]): self._link(paper_id,law,NodeType.LAW,EdgeType.MAPS_TO)
        for ax in framework_data.get("axiom_schemata",[]): self._link(paper_id,ax,NodeType.AXIOM_SCHEMA,EdgeType.MAPS_TO)
        for eq in framework_data.get("equations_present",[]): self._link(paper_id,eq,NodeType.EQUATION,EdgeType.DERIVES_FROM)
        for fr in framework_data.get("fruits_referenced",[]): self._link(paper_id,fr,NodeType.FRUIT,EdgeType.ILLUSTRATES)
        if framework_data.get("seven_q"): self._link(paper_id,framework_data["seven_q"],NodeType.SEVEN_Q,EdgeType.PART_OF)
    def _link(self,a,b,nt,et): self.nodes.setdefault(b,{"node_type":nt.value}); self.adj[a][b]=et.value; self.adj[b][a]=et.value
    def find_gaps(self)->list[dict]: return [{"node":n,"type":"missing"} for n in [f"L{i}" for i in range(1,11)]+[f"AS-00{i}" for i in range(8)] if n not in self.nodes]
    def find_clusters(self)->list[set]:
        seen=set(); clusters=[]
        for n in self.nodes:
            if n in seen: continue
            q=[n]; comp=set()
            while q:
                c=q.pop();
                if c in seen: continue
                seen.add(c); comp.add(c); q.extend(self.adj[c].keys())
            if len(comp)>1: clusters.append(comp)
        return clusters
    def shortest_path(self, from_id: str, to_id: str) -> list:
        q=deque([[from_id]]); seen={from_id}
        while q:
            p=q.popleft(); n=p[-1]
            if n==to_id: return p
            for nxt in self.adj[n]:
                if nxt not in seen: seen.add(nxt); q.append(p+[nxt])
        raise ValueError('no path')
    def coverage_report(self)->dict:
        laws={f"L{i}":0 for i in range(1,11)}; axioms={f"AS-00{i}":0 for i in range(8)}
        for a,m in self.adj.items():
            for b,e in m.items():
                if e==EdgeType.MAPS_TO.value:
                    if a in laws: laws[a]+=1
                    if b in laws: laws[b]+=1
                    if a in axioms: axioms[a]+=1
                    if b in axioms: axioms[b]+=1
        return {"laws":laws,"axioms":axioms,"gaps":self.find_gaps()}
    def export_obsidian_links(self,paper_id:str)->str: return "\n".join([f"- [[{n}]] ({e})" for n,e in self.adj.get(paper_id,{}).items()])
    def export_graph_json(self,path:Path)->None: path.write_text(json.dumps({"nodes":[{"id":k,**v} for k,v in self.nodes.items()],"edges":[{"source":a,"target":b,"edge_type":e} for a,m in self.adj.items() for b,e in m.items() if a<b]},indent=2),encoding='utf-8')
    def export_mermaid(self,center_node:str,depth:int=2)->str:
        lines=["graph TD"]; frontier={center_node}; seen={center_node}
        for _ in range(depth):
            nxt=set()
            for a in frontier:
                for b in self.adj.get(a,{}): lines.append(f"  {a} --- {b}"); nxt.add(b)
            frontier=nxt-seen; seen|=nxt
        return "\n".join(lines)
