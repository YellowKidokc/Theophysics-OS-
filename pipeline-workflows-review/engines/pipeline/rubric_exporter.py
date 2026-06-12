from __future__ import annotations
import json
from pathlib import Path

class RubricExporter:
    def __init__(self, output_dir: Path): self.output_dir=output_dir; self.output_dir.mkdir(parents=True,exist_ok=True)
    def collect_sidecars(self,paper_dir:Path,paper_id:str)->dict:
        data={}
        for f in paper_dir.glob(f"{paper_id}*"):
            if f.suffix=='.json': data[f.name]=json.loads(f.read_text(encoding='utf-8'))
        return data
    def _sheet(self,wb,name,rows):
        ws=wb.create_sheet(name); [ws.append(r) for r in rows] if rows else ws.append(["Not yet processed"])
    def build_excel(self,paper_id:str,data:dict)->Path:
        composite=self._composite(data)
        payload={"OVERVIEW":[["paper_id",paper_id],["overall_score",composite],["verdict",self._verdict(composite)]],"CLASSIFICATION":[["Not yet processed"]],"FACT CHECK":[["Not yet processed"]],"MATH CHECK":[["Not yet processed"]],"CONTRADICTION CHECK":[["Not yet processed"]],"TIMELINE CHECK":[["Not yet processed"]],"QUALITY GRADE":[["Not yet processed"]],"MEDIA ROUTING":[["Not yet processed"]],"COMPOSITE SCORES":[["composite",composite],["verdict",self._verdict(composite)]]}
        p=self.output_dir/f"{paper_id}_RUBRIC.xlsx"; p.write_text(json.dumps(payload,indent=2),encoding="utf-8"); return p
    def _composite(self,data):
        c=(data.get('score',{}) if isinstance(data.get('score',{}),dict) else {})
        keys={"classification":.1,"fact_check":.2,"math":.15,"contradiction":.15,"timeline":.1,"coherence":.1,"voice":.05,"cross_domain":.1,"publish_readiness":.05}
        return round(sum(float(c.get(k,0))*w for k,w in keys.items()),3)
    def _verdict(self,s): return 'PUBLISH' if s>0.8 else 'REVISE' if s>0.6 else 'RESTRUCTURE' if s>0.4 else 'HOLD'
    def build_html(self,paper_id:str,data:dict)->Path:
        composite=self._composite(data)
        html=f"<html><body style='background:#0d1117;color:#e6d5a8'><h1>{paper_id}</h1><div>Score:{composite}</div><svg width='240' height='240'><circle cx='120' cy='120' r='90' stroke='#c9a227' fill='none'/></svg><a href='{paper_id}_RUBRIC.xlsx'>Excel</a></body></html>"
        p=self.output_dir/f"{paper_id}_REPORT.html"; p.write_text(html,encoding='utf-8'); return p
    def export(self,paper_dir:Path,paper_id:str): d=self.collect_sidecars(paper_dir,paper_id); return self.build_excel(paper_id,d),self.build_html(paper_id,d)
