"""Reprocess archived BrainHandoff transcripts over 500 bytes."""
from pathlib import Path
from process_transcript import process_file

if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    for fp in (root / 'ARCHIVE').glob('*'):
        if fp.is_file() and fp.stat().st_size > 500:
            process_file(fp, root)
