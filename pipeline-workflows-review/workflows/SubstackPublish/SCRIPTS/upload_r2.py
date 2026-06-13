"""Upload prepared publish assets to R2-compatible endpoint."""
import json, os
from pathlib import Path

def run():
    root=Path(__file__).resolve().parents[1]
    out=root/'OUTPUT'; log=[]
    for f in out.glob('*'):
        log.append({'file':f.name,'bucket':os.environ.get('R2_BUCKET','theophysics'),'uploaded':False})
    (root/'LOGS').mkdir(exist_ok=True)
    (root/'LOGS'/'r2_upload_log.json').write_text(json.dumps(log,indent=2),encoding='utf-8')
if __name__=='__main__': run()
