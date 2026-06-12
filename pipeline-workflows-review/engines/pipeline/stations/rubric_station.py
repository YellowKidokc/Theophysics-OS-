from __future__ import annotations
from pathlib import Path
from ..rubric_exporter import RubricExporter
from ..station_base import Manifest, StationBase, StationVerdict

class RubricStation(StationBase):
    """Final export station for rubric outputs."""
    def __init__(self,input_dir:str,output_dir:str,**kwargs):
        super().__init__("rubric-export",input_dir,output_dir,file_extensions=[".md",".txt"],**kwargs)
        self.exporter=RubricExporter(Path(output_dir))
    def process(self,file_path:Path,manifest:Manifest):
        self.exporter.export(file_path.parent,file_path.stem)
        return StationVerdict.PASS,1.0,"rubric exported"
