import json
import subprocess

from engines.pipeline.external_adapter import ExternalStationAdapter
from engines.pipeline.station_base import Manifest, StationVerdict


def test_external_adapter_from_registry(tmp_path):
    station_root = tmp_path / "mock.station"
    (station_root / "INPUT").mkdir(parents=True)
    (station_root / "OUTPUT").mkdir()
    (station_root / "RUN.bat").write_text("echo ok", encoding="utf-8")
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps({"stations": {"mock": {"path": str(station_root), "has_run_bat": True}}}), encoding="utf-8")

    adapter = ExternalStationAdapter.from_registry("mock", registry_path=str(registry))

    assert adapter.name == "mock"
    assert adapter.station_path == station_root
    assert adapter.run_bat.exists()


def test_external_adapter_process_mock(monkeypatch, tmp_path):
    station_root = tmp_path / "mock.station"
    (station_root / "INPUT").mkdir(parents=True)
    (station_root / "OUTPUT").mkdir()
    (station_root / "RUN.bat").write_text("echo ok", encoding="utf-8")
    source = tmp_path / "source.txt"
    source.write_text("hello", encoding="utf-8")

    def fake_run(*args, **kwargs):
        (station_root / "OUTPUT" / "source.out").write_text("done", encoding="utf-8")
        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    adapter = ExternalStationAdapter("mock", str(station_root), str(station_root / "INPUT"), str(station_root / "OUTPUT"))
    manifest = Manifest(file_path=str(source), file_hash="h", pipeline_name="p", current_station="mock")

    verdict, score, notes = adapter.process(source, manifest)

    assert verdict == StationVerdict.PASS
    assert score == 1.0
    assert "Exit 0" in notes
    assert (station_root / "INPUT" / source.name).read_text(encoding="utf-8") == "hello"
