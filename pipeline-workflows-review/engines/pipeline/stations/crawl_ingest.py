from __future__ import annotations
import json
from pathlib import Path
from ..station_base import Manifest, StationBase, StationVerdict

class CrawlIngestStation(StationBase):
    def __init__(self,input_dir:str,output_dir:str,**kwargs):
        super().__init__('crawl-ingest',input_dir,output_dir,file_extensions=['.json'],**kwargs)
    def process(self,file_path:Path,manifest:Manifest):
        rows=json.loads(file_path.read_text(encoding='utf-8'))
        out=[]
        for r in rows if isinstance(rows,list) else [rows]:
            out.append(f"# {r.get('title','untitled')}\n\n{r.get('content','')}\n")
        md=self.output_dir/f'{file_path.stem}.md'; md.write_text('\n\n'.join(out),encoding='utf-8')
        return StationVerdict.PASS,0.85,'crawler content normalized'
