"""Run full paper mill pipeline."""
from engines.pipeline.fap_boot import create_engine


if __name__ == "__main__":
    engine = create_engine()
    engine.init_db()
    engine.start()
    engine.sweep()
