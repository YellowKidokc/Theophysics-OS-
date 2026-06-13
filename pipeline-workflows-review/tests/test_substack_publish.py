import json
from workflows.SubstackPublish.SCRIPTS.prepare_publish import prepare


def test_prepare_publish_outputs(tmp_path):
    src = tmp_path / "paper.md"
    src.write_text("## Layer 1: Executive Summary\nSummary.\n## Layer 3: The Paper\nBody text L5\n## Layer 4:")
    out = tmp_path / "out"
    res = prepare(src, out)
    assert (out / "paper.html").exists()
    meta = json.loads((out / "paper_meta.json").read_text())
    assert meta["slug"] == "paper"
