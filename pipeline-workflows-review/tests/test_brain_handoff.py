import json
from pathlib import Path
from workflows.BrainHandoff.SCRIPTS.process_transcript import process_file


def test_transcript_processing_outputs(tmp_path):
    root = tmp_path
    for d in ["INPUT", "OUTPUT", "ARCHIVE", "LOGS"]:
        (root / d).mkdir()
    fp = root / "INPUT" / "session.md"
    fp.write_text("We decided to build L5 mapping and action items.")
    result = process_file(fp, root)
    assert Path(result["summary_json"]).exists()
    data = json.loads(Path(result["summary_json"]).read_text())
    assert "key_decisions" in data
