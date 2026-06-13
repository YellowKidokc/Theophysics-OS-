import json
from engines.pipeline.rubric_exporter import RubricExporter


def test_rubric_exporter_outputs(tmp_path):
    (tmp_path/'P1.fap.json').write_text(json.dumps({'doc_type':'paper'}))
    ex=RubricExporter(tmp_path/'out')
    x,h=ex.export(tmp_path,'P1')
    assert x.exists() and h.exists()
    payload=json.loads(x.read_text())
    assert payload['FACT CHECK'][0][0]=='Not yet processed'
