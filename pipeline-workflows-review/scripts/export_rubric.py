import argparse
from pathlib import Path
from engines.pipeline.rubric_exporter import RubricExporter
if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--paper-dir',required=True); ap.add_argument('--paper-id',required=True); ap.add_argument('--out',required=True)
    a=ap.parse_args(); x,h=RubricExporter(Path(a.out)).export(Path(a.paper_dir),a.paper_id); print(x,h)
