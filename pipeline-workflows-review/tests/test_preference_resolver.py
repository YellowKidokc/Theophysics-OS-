from scripts.resolve_preferences import resolve


def test_resolve_priority_and_missing_profile():
    base = resolve("PaperGrading", profile_name="does_not_exist")
    assert "threshold_pass" in base

    with_override = resolve("PaperGrading", overrides={"threshold_pass": 0.95})
    assert with_override["threshold_pass"] == 0.95
