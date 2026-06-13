from workflows.CorpusTriage.SCRIPTS.triage_folder import triage


def test_triage_inventory_and_outputs(tmp_path):
    src = tmp_path / "src"; src.mkdir()
    (src / "a.md").write_text("L1 grace " * 220)
    out = tmp_path / "out"
    summary = triage(src, out)
    assert summary["total"] >= 1
    assert (out / "triage_manifest.json").exists()
    assert (out / "duplicates.json").exists()
