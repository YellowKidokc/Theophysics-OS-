import json
from pathlib import Path
from workflows.CorpusTriage.SCRIPTS.run_packet import sha


def test_corpus_sha(tmp_path):
    p=tmp_path/'a.txt'; p.write_text('x')
    assert len(sha(p))==64


def test_brain_prefs_exists():
    data=json.loads(Path('workflows/BrainHandoff/PREFS/preferences.json').read_text())
    assert data['workflow']=='BrainHandoff'
