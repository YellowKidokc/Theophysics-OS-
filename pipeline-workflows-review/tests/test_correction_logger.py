from scripts.correction_logger import CorrectionLogger


def test_correction_logger_log_read_stats(tmp_path, monkeypatch):
    logger = CorrectionLogger(log_dir=str(tmp_path), bil_endpoint="http://localhost:1")
    monkeypatch.setattr(logger, "_push_to_bil", lambda event: None)
    source = tmp_path / "doc.md"
    source.write_text("hello", encoding="utf-8")

    event = logger.log_correction(
        file_path=str(source),
        stage="classify",
        old_verdict="review",
        new_verdict="pass",
        reason="manual override",
        workflow="sandbox-file-intake",
    )

    corrections = logger.get_corrections()
    stats = logger.get_stats()
    assert event["event_type"] == "human_correction"
    assert corrections[-1]["stage"] == "classify"
    assert stats["total_corrections"] == 1
    assert stats["by_stage"] == {"classify": 1}
