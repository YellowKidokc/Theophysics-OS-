import json
from engines.pipeline.knowledge_graph import KnowledgeGraph


def test_build_and_report(tmp_path):
    (tmp_path/'doc.framework.json').write_text(json.dumps({'laws_referenced':['L1'],'axiom_schemata':['AS-000'],'equations_present':['entropy_kernel'],'fruits_referenced':['love'],'seven_q':'Q4_Moral','framework_coverage_score':0.7}))
    kg=KnowledgeGraph(); kg.build_from_sidecars(tmp_path)
    report=kg.coverage_report()
    assert report['laws']['L1']>=1
    assert 'L2' in [g['node'] for g in report['gaps']]
