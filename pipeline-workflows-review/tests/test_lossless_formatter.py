from engines.pipeline.station_base import Manifest
from engines.pipeline.stations.lossless_formatter import LosslessFormatterStation


def test_lossless_cleanup_markdown_and_metadata(tmp_path):
    src = tmp_path / "n.txt"
    src.write_text("#Title\n\num um this this is <b>text</b>\r\n-thing")
    (tmp_path / "n.txt.fap.json").write_text('{"doc_type":"paper"}')
    m = Manifest(file_path=str(src), file_hash="h", pipeline_name="p", current_station="lossless")
    st = LosslessFormatterStation(str(tmp_path), str(tmp_path / "out"))
    verdict, score, _ = st.process(src, m)
    out = (tmp_path / "out" / "n.md").read_text()
    assert verdict.value in {"pass", "review"}
    assert score > 0
    assert "title:" in out and "classification:" in out
    assert "# Title" in out and "- thing" in out
