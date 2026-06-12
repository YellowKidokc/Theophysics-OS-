from engines.pipeline.station_base import Manifest
from engines.pipeline.stations.vectorizer import VectorizerStation


def test_vectorizer_chunk_sidecar_and_duplicate(tmp_path):
    out = tmp_path / "out"
    st = VectorizerStation(str(tmp_path), str(out))
    m = Manifest(file_path=str(tmp_path / "v.md"), file_hash="h", pipeline_name="p", current_station="v")

    first = tmp_path / "v.md"; first.write_text("# H\n\n" + ("word " * 520))
    st.process(first, m)
    assert (tmp_path / "v.md.vectors.json").exists()

    second = tmp_path / "v2.md"; second.write_text(first.read_text())
    st.process(second, m)
    assert any(s.signal_type.value == "duplicate" for s in st.drain_signals())
