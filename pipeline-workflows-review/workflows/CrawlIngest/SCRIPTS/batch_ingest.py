from pathlib import Path
from ingest_crawl import ingest_file

if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    for fp in (root/'INPUT').glob('*.json'):
        ingest_file(fp, root)
