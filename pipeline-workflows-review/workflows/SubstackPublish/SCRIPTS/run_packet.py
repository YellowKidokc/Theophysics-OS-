from __future__ import annotations
import argparse
from pathlib import Path
from engines.pipeline.station_base import Manifest
from engines.pipeline.stations.substack_publish import SubstackPublishStation
if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--input',required=True); ap.add_argument('--output',required=True)
    a=ap.parse_args(); st=SubstackPublishStation(a.input,a.output)
    for fp in Path(a.input).glob('*.md'):
        m=Manifest(file_path=str(fp),file_hash='-',pipeline_name='substack',current_station='substack-publish'); st.process(fp,m)
