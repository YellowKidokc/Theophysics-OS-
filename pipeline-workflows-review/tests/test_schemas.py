import json
from pathlib import Path

try:
    from jsonschema import Draft202012Validator
except ImportError:  # pragma: no cover - CI may not install jsonschema
    Draft202012Validator = None


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def assert_required_keys(data, schema):
    for key in schema.get("required", []):
        assert key in data, f"missing required key {key}"


def validate(data, schema):
    assert_required_keys(data, schema)
    if Draft202012Validator is not None:
        Draft202012Validator(schema).validate(data)


def test_schema_files_are_draft_2020_12_json():
    for path in Path("schemas").glob("*.json"):
        schema = load(path)
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema.get("type") == "object"


def test_station_configs_validate_against_station_schema():
    schema = load("schemas/station.schema.json")
    for path in Path("stations").glob("*/*.json"):
        validate(load(path), schema)


def test_workflows_validate_against_workflow_schema():
    schema = load("schemas/workflow.schema.json")
    for path in Path("workflows").glob("*.json"):
        if path.name == "WORKFLOW_REGISTRY.json":
            continue
        validate(load(path), schema)


def test_registries_and_pipeline_config_are_valid_json():
    station_registry = load("stations/STATION_REGISTRY.json")
    model_registry = load("models/MODEL_REGISTRY.json")
    workflow_registry = load("workflows/WORKFLOW_REGISTRY.json")
    config = load("pipeline.config.json")

    assert len(station_registry["stations"]) >= 47
    assert station_registry["_meta"]["canary_summary"]
    assert model_registry
    assert workflow_registry["workflows"]["sandbox-file-intake"]["phase"] == 0
    assert config["doctrine"]["vectorize_before_classify"] is True
