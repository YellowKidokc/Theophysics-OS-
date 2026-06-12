import json

from scripts.orchestrator import Orchestrator


def make_packet(tmp_path):
    packet = tmp_path / "packet"
    (packet / "INPUT").mkdir(parents=True)
    (packet / "INPUT" / "sample.txt").write_text("hello", encoding="utf-8")
    return packet


def test_orchestrator_resolves_dag_and_writes_state(tmp_path):
    workflow = tmp_path / "workflow.json"
    workflow.write_text(json.dumps({
        "name": "mock-flow",
        "version": "1.0",
        "stages": [
            {"name": "vectorize", "station": "sbert-embedder", "on_error": "stop", "depends_on": []},
            {"name": "classify", "station": "classify-documents", "on_error": "stop", "depends_on": ["vectorize"]},
        ],
    }), encoding="utf-8")
    packet = make_packet(tmp_path)
    manifest = tmp_path / "MANIFEST.json"

    status = Orchestrator(manifest_path=manifest, dry_run=True).run(workflow, packet, resume=False)

    assert status["status"] == "completed"
    assert [h["stage"] for h in status["history"]] == ["vectorize", "classify"]
    assert (packet / "STATUS.json").exists()
    assert json.loads(manifest.read_text(encoding="utf-8"))["packets"][0]["status"] == "completed"


def test_orchestrator_parallel_stage_and_llm_gate(tmp_path):
    workflow = tmp_path / "workflow.json"
    workflow.write_text(json.dumps({
        "name": "parallel-flow",
        "version": "1.0",
        "stages": [{
            "name": "framework-check",
            "station": "fruits-spirit-canon",
            "stations": ["fruits-spirit-canon", "trinity-canon"],
            "parallel": True,
            "on_error": "continue",
            "depends_on": [],
            "llm_gate": {"enabled": True, "engine": "ollama:phi4", "prompt": "pass?"},
        }],
    }), encoding="utf-8")
    packet = make_packet(tmp_path)

    status = Orchestrator(manifest_path=tmp_path / "MANIFEST.json", dry_run=True).run(workflow, packet, resume=False)

    assert status["status"] == "completed"
    assert status["history"][0]["stage"] == "framework-check"
    assert "dry-run llm gate" in status["history"][0]["notes"]


def test_orchestrator_error_handling_stop(tmp_path):
    workflow = tmp_path / "workflow.json"
    workflow.write_text(json.dumps({
        "name": "bad-flow",
        "version": "1.0",
        "stages": [{"name": "missing", "station": "not-in-registry", "on_error": "stop", "depends_on": []}],
    }), encoding="utf-8")
    packet = make_packet(tmp_path)

    status = Orchestrator(manifest_path=tmp_path / "MANIFEST.json", dry_run=False).run(workflow, packet, resume=False)

    assert status["status"] == "failed"
    assert status["errors"]
