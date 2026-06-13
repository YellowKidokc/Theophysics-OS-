import json

from engines.pipeline.station_base import Manifest, SignalType, StationBase, StationVerdict
from engines.pipeline.station_runner import StationRunner


class GoodStation(StationBase):
    def __init__(self, root: str):
        super().__init__("good", root, root)

    def process(self, file_path, manifest):
        self.emit_signal(SignalType.UPSTREAM, "ok")
        return StationVerdict.PASS, 0.8, "done"


class BadStation(StationBase):
    def __init__(self, root: str):
        super().__init__("bad", root, root)

    def process(self, file_path, manifest):
        raise RuntimeError("boom")


def test_runner_logs_and_routes_signals(tmp_path):
    fp = tmp_path / "a.txt"; fp.write_text("x")
    manifest = Manifest(file_path=str(fp), file_hash="h", pipeline_name="p", current_station="good")
    station = GoodStation(str(tmp_path))
    seen = []
    runner = StationRunner(workflow_name="PaperGrading", log_dir=str(tmp_path))
    verdict, _, _, signals = runner.run(station, fp, manifest, signal_handler=lambda s: seen.append(s.signal_type.value))
    assert verdict == StationVerdict.PASS
    assert seen == ["upstream"]
    assert signals and signals[0].signal_type.value == "upstream"
    row = json.loads((tmp_path / "station_runs.jsonl").read_text().splitlines()[0])
    assert row["station_name"] == "good"


def test_runner_handles_exception(tmp_path):
    fp = tmp_path / "e.txt"; fp.write_text("x")
    manifest = Manifest(file_path=str(fp), file_hash="h", pipeline_name="p", current_station="bad")
    verdict, score, notes, signals = StationRunner(log_dir=str(tmp_path)).run(BadStation(str(tmp_path)), fp, manifest)
    assert verdict == StationVerdict.FAIL
    assert score == 0.0
    assert "exception" in notes.lower()
    assert any(s.signal_type.value == "error" for s in signals)
