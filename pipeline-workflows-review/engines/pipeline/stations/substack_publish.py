"""Substack publish station: html package + metadata + upload queue."""
from __future__ import annotations
import json
from pathlib import Path
from ..station_base import Manifest, StationBase, StationVerdict

class SubstackPublishStation(StationBase):
    def __init__(self,input_dir:str,output_dir:str,**kwargs):
        super().__init__('substack-publish',input_dir,output_dir,file_extensions=['.md'],**kwargs)
    def process(self,file_path:Path,manifest:Manifest):
        text=file_path.read_text(encoding='utf-8',errors='replace')
        html=f"<html><head><meta property='og:title' content='{file_path.stem}'></head><body style='background:#0d1117;color:#e6d5a8'>{text}</body></html>"
        out=self.output_dir/f'{file_path.stem}.html'; out.write_text(html,encoding='utf-8')
        (self.output_dir/f'{file_path.stem}.publish.json').write_text(json.dumps({'r2_queue':True,'source':file_path.name},indent=2),encoding='utf-8')
        return StationVerdict.PASS,0.9,'substack package generated'
