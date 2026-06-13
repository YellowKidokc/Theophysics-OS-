"""Deep framework classifier station."""
from __future__ import annotations
import json,re
from pathlib import Path
from ..llm_hub import LLMHub
from ..station_base import Manifest, SignalType, StationBase, StationVerdict
from ..framework_registry import *

class FrameworkClassifierStation(StationBase):
    """Tag papers against Theophysics formal apparatus."""
    def __init__(self,input_dir:str,output_dir:str,queue_dir:str|None=None,**kwargs):
        super().__init__("framework-classifier",input_dir,output_dir,file_extensions=[".md",".txt"],**kwargs)
        self.hub=LLMHub(queue_dir=queue_dir or "_queue")

    def process(self,file_path:Path,manifest:Manifest)->tuple[StationVerdict,float,str]:
        text=file_path.read_text(encoding="utf-8",errors="replace")
        data=self._rule_tag(text,file_path)
        sidecar=file_path.with_suffix(file_path.suffix+".framework.json")
        sidecar.write_text(json.dumps(data,indent=2),encoding="utf-8")
        manifest.metadata["framework"]=data
        if data["framework_coverage_score"]<0.25:
            self.emit_signal(SignalType.GAP,"Low framework coverage",{"paper":file_path.name})
        return (StationVerdict.PASS if data["confidence"]>=self.threshold_pass else StationVerdict.REVIEW,data["confidence"],"framework classified")

    def _contains(self,text:str,terms:list[str])->list[str]:
        t=text.lower();return [x for x in terms if x.lower() in t]

    def _rule_tag(self,text:str,file_path:Path)->dict:
        master=[k for k,v in MASTER_EQUATION.items() if k.lower() in text.lower() or v.split('/')[0].lower() in text.lower()]
        laws=[k for k,v in LAWS.items() if v['name'].lower() in text.lower() or k.lower() in text.lower()]
        sym=[f"{k}↔{LAWS[k]['sym_pair']}" for k in laws if LAWS.get(k,{}).get('sym_pair') and LAWS[k]['sym_pair'] in laws]
        fruits=self._contains(text,list(FRUITS.keys())); anti=self._contains(text,ANTI_FRUITS)
        jm={k:(k in text.lower()) for k in ["justice","mercy","cross"]}
        moral=[k for k in MORAL_CONSERVATION if k.replace('_',' ') in text.lower() or k in text.lower()]
        trinity=[k for k in TRINITY if k in text.lower()]
        eq=[k for k in KEY_EQUATIONS if k.replace('_',' ') in text.lower() or KEY_EQUATIONS[k].split('=')[0].strip().lower() in text.lower()]
        axioms=[k for k,v in AXIOM_SCHEMATA.items() if k.lower() in text.lower() or v.lower() in text.lower()]
        seven=next((q for q in SEVEN_Q if q.lower() in text.lower()),"Q4_Moral")
        exp=[k for k in EXPERIMENTAL if k.replace('_',' ') in text.lower()]
        covered=sum(bool(x) for x in [master,laws,fruits,jm,moral,trinity,eq,axioms,exp])
        coverage=covered/9
        return {"paper_id":file_path.stem,"master_equation_variables":master,"laws_referenced":laws,"law_symmetry_pairs_invoked":sym,"fruits_referenced":fruits,"anti_fruits_referenced":anti,"justice_mercy":jm,"moral_conservation":moral,"trinity_aspects":trinity,"equations_present":eq,"axiom_schemata":axioms,"seven_q":seven,"experimental_refs":exp,"framework_coverage_score":round(coverage,2),"framework_depth":"deep" if coverage>0.66 else "medium" if coverage>0.33 else "shallow","confidence":round(min(1.0,0.35+coverage*0.6),2)}
