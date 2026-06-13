import json
from workflows.CrawlIngest.SCRIPTS.ingest_crawl import ingest_file


def test_crawl_ingest_parsing(tmp_path):
    root = tmp_path
    for d in ["INPUT", "OUTPUT", "ARCHIVE", "LOGS"]:
        (root / d).mkdir()
    src = root / "INPUT" / "c.json"
    src.write_text(json.dumps({"url": "http://x", "title": "t", "text": "L1 AS-000"}))
    rep = ingest_file(src, root)
    assert rep["url"] == "http://x"
    assert (root / "OUTPUT" / "c.md").exists()
