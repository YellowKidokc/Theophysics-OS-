import json

from engines.pipeline.station_base import Manifest, StationVerdict
from engines.pipeline.stations.paper_grader import PaperGraderStation


def test_submit_and_collect_modes(tmp_path):
    src = tmp_path / "g.md"; src.write_text("hello")
    queue = tmp_path / "q"
    st = PaperGraderStation(str(tmp_path), str(tmp_path / "out"), queue_dir=str(queue))
    m = Manifest(file_path=str(src), file_hash="h", pipeline_name="p", current_station="paper-grader")
    verdict, _, _ = st.process(src, m)
    assert verdict == StationVerdict.HOLD

    job_id = json.loads((tmp_path / "g.md.grade.json").read_text())["job_id"]
    done = queue / "completed" / f"{job_id}.json"
    done.parent.mkdir(parents=True, exist_ok=True)
    done.write_text(json.dumps({"result_json": {"overall_score": 0.91}}))
    verdict, score, _ = st.process(src, m)
    assert verdict == StationVerdict.PASS
    assert score > 0.9
