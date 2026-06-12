import json
from engines.pipeline.station_base import Manifest
from engines.pipeline.stations.framework_classifier import FrameworkClassifierStation


def test_framework_classifier_sidecar(tmp_path):
    src=tmp_path/'p.md'; src.write_text('L5 justice mercy cross AS-005 grace moral conservation Christ coherence')
    st=FrameworkClassifierStation(str(tmp_path),str(tmp_path/'out'),queue_dir=str(tmp_path/'q'))
    m=Manifest(file_path=str(src),file_hash='h',pipeline_name='p',current_station='framework-classifier')
    verdict,score,_=st.process(src,m)
    data=json.loads((tmp_path/'p.md.framework.json').read_text())
    assert verdict.value in {'pass','review'}
    assert data['laws_referenced']
    assert score>0
