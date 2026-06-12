import json

from engines.pipeline.station_base import Manifest, StationVerdict
from engines.pipeline.stations.axiom_mapper import AxiomMapperStation


def test_claim_collect_and_signals(tmp_path):
    src = tmp_path / "a.md"; src.write_text("claim")
    queue = tmp_path / "q"
    st = AxiomMapperStation(str(tmp_path), str(tmp_path / "out"), queue_dir=str(queue))
    m = Manifest(file_path=str(src), file_hash="h", pipeline_name="p", current_station="axiom-mapper")

    assert st.process(src, m)[0] == StationVerdict.HOLD
    job_id = json.loads((tmp_path / "a.md.axioms.json").read_text())["job_id"]
    done = queue / "completed" / f"{job_id}.json"
    done.parent.mkdir(parents=True, exist_ok=True)
    done.write_text(json.dumps({"result_json": {"claims": ["c1"], "mappings": [{"axiom": "A1"}], "gaps": ["A2"], "contradictions": ["c1"], "confidence": 0.9}}))

    verdict, score, _ = st.process(src, m)
    assert verdict in (StationVerdict.PASS, StationVerdict.REVIEW)
    assert score > 0
    sigs = st.drain_signals()
    assert any(s.signal_type.value == "gap" for s in sigs)
    assert any(s.signal_type.value == "quality" for s in sigs)
