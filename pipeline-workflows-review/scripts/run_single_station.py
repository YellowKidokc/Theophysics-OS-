"""Run one station against one file."""
import argparse
from pathlib import Path

from engines.pipeline.fap_boot import create_engine


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("station")
    parser.add_argument("file")
    args = parser.parse_args()
    engine = create_engine()
    station = engine.stations[args.station]
    engine._handle_file(station, Path(args.file))
