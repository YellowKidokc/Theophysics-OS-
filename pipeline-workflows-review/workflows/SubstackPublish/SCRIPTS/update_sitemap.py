import json
from pathlib import Path

def run():
    root=Path(__file__).resolve().parents[1]
    sitemap=root/'OUTPUT'/'sitemap.json'
    items=json.loads(sitemap.read_text()) if sitemap.exists() else []
    for meta in (root/'OUTPUT').glob('*_meta.json'):
        data=json.loads(meta.read_text())
        if not any(i.get('slug')==data['slug'] for i in items): items.append({'slug':data['slug'],'url':data['url']})
    sitemap.write_text(json.dumps(items,indent=2),encoding='utf-8')
if __name__=='__main__': run()
