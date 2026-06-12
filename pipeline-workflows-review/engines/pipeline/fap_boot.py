"""
fap_boot.py — Bootstrap script for Folder Automations & Pipelines.

Run this to:
  1. Initialize Postgres schema
  2. Register the Paper Mill pipeline with all stations
  3. Create hot folder directories
  4. Start the FAP engine (or integrate into BIL service)

Usage:
  python fap_boot.py              # standalone
  python fap_boot.py --init-db    # just create schema
  python fap_boot.py --dry-run    # show what would happen

Integration with BIL:
  from engines.pipeline.fap_boot import create_engine
  engine = create_engine()
  engine.start()  # in a thread alongside BIL
"""

import argparse
import sys
import os
import logging
from pathlib import Path

# Add BIL root to path
BIL_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BIL_ROOT))

from engines.pipeline.pipeline_engine import PipelineEngine
from engines.pipeline.stations.classifier import ClassifierStation
from engines.pipeline.stations.media_transformer import MediaTransformStation
from engines.pipeline.stations.lossless_formatter import LosslessFormatterStation
from engines.pipeline.stations.vectorizer import VectorizerStation
from engines.pipeline.stations.paper_grader import PaperGraderStation
from engines.pipeline.stations.axiom_mapper import AxiomMapperStation
from engines.pipeline.stations.wiki_compiler import WikiCompilerStation
from engines.pipeline.stations.framework_classifier import FrameworkClassifierStation
from engines.pipeline.stations.rubric_station import RubricStation

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("FAP-Boot")

# ══════════════════════════════════════════════════════════════════
# FAP DIRECTORY STRUCTURE
# ══════════════════════════════════════════════════════════════════
FAP_ROOT = os.environ.get("FAP_ROOT", r"D:\FAP")
DIRS = {
    "intake":         os.path.join(FAP_ROOT, "intake"),
    "classified":     os.path.join(FAP_ROOT, "classified"),
    "media_routed":   os.path.join(FAP_ROOT, "media-routed"),
    "lossless":       os.path.join(FAP_ROOT, "lossless"),
    "framework_tagged": os.path.join(FAP_ROOT, "framework-tagged"),
    "vectorized":     os.path.join(FAP_ROOT, "vectorized"),
    "graded":         os.path.join(FAP_ROOT, "graded"),
    "axiom_mapped":   os.path.join(FAP_ROOT, "axiom-mapped"),
    "output":         os.path.join(FAP_ROOT, "output"),
    "rubric_output":  os.path.join(FAP_ROOT, "rubric-output"),
    "review":         os.path.join(FAP_ROOT, "_review"),
    "rejected":       os.path.join(FAP_ROOT, "_rejected"),
    "wiki":           os.path.join(FAP_ROOT, "wiki"),
    "queue":          os.path.join(FAP_ROOT, "_queue"),
    "logs":           os.path.join(FAP_ROOT, "logs"),
}

PG_DSN = os.environ.get("FAP_PG_DSN", "")

ALL_STATIONS = [
    "classifier", "media-transform-router", "lossless-formatter",
    "framework-classifier", "vectorizer", "paper-grader",
    "axiom-mapper", "wiki-compiler", "rubric-export",
]


def create_directories():
    for name, path in DIRS.items():
        os.makedirs(path, exist_ok=True)
        logger.info(f"  Dir: {path}")
    for station in ALL_STATIONS:
        os.makedirs(os.path.join(DIRS["review"], station), exist_ok=True)
        os.makedirs(os.path.join(DIRS["rejected"], station), exist_ok=True)


def create_engine(pg_dsn: str = None) -> PipelineEngine:
    """Create and configure the FAP engine with Paper Mill pipeline."""
    engine = PipelineEngine(pg_dsn=pg_dsn or PG_DSN)

    # Station 1: Classifier
    engine.register_station(ClassifierStation(
        input_dir=DIRS["intake"],
        output_dir=DIRS["classified"],
        review_dir=os.path.join(DIRS["review"], "classifier"),
        fail_dir=os.path.join(DIRS["rejected"], "classifier"),
        threshold_pass=0.6, threshold_fail=0.25,
    ), pipeline_name="paper-mill", order=1)

    # Station 2: Media/text route
    engine.register_station(MediaTransformStation(
        input_dir=DIRS["classified"],
        output_dir=DIRS["media_routed"],
        lane_root=DIRS["media_routed"],
        review_dir=os.path.join(DIRS["review"], "media-transform-router"),
        fail_dir=os.path.join(DIRS["rejected"], "media-transform-router"),
        threshold_pass=0.55, threshold_fail=0.25,
    ), pipeline_name="paper-mill", order=2)

    # Station 3: Lossless formatter
    engine.register_station(LosslessFormatterStation(
        input_dir=DIRS["media_routed"],
        output_dir=DIRS["lossless"],
        review_dir=os.path.join(DIRS["review"], "lossless-formatter"),
        fail_dir=os.path.join(DIRS["rejected"], "lossless-formatter"),
    ), pipeline_name="paper-mill", order=3)

    # Station 4: Framework classifier (deep formal tagging)
    engine.register_station(FrameworkClassifierStation(
        input_dir=DIRS["lossless"],
        output_dir=DIRS["framework_tagged"],
        review_dir=os.path.join(DIRS["review"], "framework-classifier"),
        fail_dir=os.path.join(DIRS["rejected"], "framework-classifier"),
    ), pipeline_name="paper-mill", order=4)

    # Station 5: Vectorizer
    engine.register_station(VectorizerStation(
        input_dir=DIRS["framework_tagged"],
        output_dir=DIRS["vectorized"],
        review_dir=os.path.join(DIRS["review"], "vectorizer"),
        fail_dir=os.path.join(DIRS["rejected"], "vectorizer"),
    ), pipeline_name="paper-mill", order=5)

    # Station 6: Paper grader (LLM Hub)
    engine.register_station(PaperGraderStation(
        input_dir=DIRS["vectorized"],
        output_dir=DIRS["graded"],
        review_dir=os.path.join(DIRS["review"], "paper-grader"),
        fail_dir=os.path.join(DIRS["rejected"], "paper-grader"),
    ), pipeline_name="paper-mill", order=6)

    # Station 7: Axiom mapper (LLM Hub)
    engine.register_station(AxiomMapperStation(
        input_dir=DIRS["graded"],
        output_dir=DIRS["axiom_mapped"],
        review_dir=os.path.join(DIRS["review"], "axiom-mapper"),
        fail_dir=os.path.join(DIRS["rejected"], "axiom-mapper"),
    ), pipeline_name="paper-mill", order=7)

    # Station 8: Wiki compiler (7-layer Obsidian page)
    engine.register_station(WikiCompilerStation(
        input_dir=DIRS["axiom_mapped"],
        output_dir=DIRS["output"],
        review_dir=os.path.join(DIRS["review"], "wiki-compiler"),
        fail_dir=os.path.join(DIRS["rejected"], "wiki-compiler"),
    ), pipeline_name="paper-mill", order=8)

    # Station 9: Rubric export (Excel + HTML report card)
    engine.register_station(RubricStation(
        input_dir=DIRS["output"],
        output_dir=DIRS["rubric_output"],
        review_dir=os.path.join(DIRS["review"], "rubric-export"),
        fail_dir=os.path.join(DIRS["rejected"], "rubric-export"),
    ), pipeline_name="paper-mill", order=9)

    # Signal handler
    def on_signal(sig):
        prefix = {
            "gap": "🔴 GAP", "duplicate": "🟡 DUPLICATE",
            "quality": "🟠 QUALITY", "ready": "🟢 READY",
            "error": "❌ ERROR",
        }.get(sig.signal_type.value, "📡 SIGNAL")
        logger.info(f"{prefix}: {sig.message}")

    engine.on_signal(on_signal)
    return engine


def main():
    parser = argparse.ArgumentParser(description="FAP Bootstrap")
    parser.add_argument("--init-db", action="store_true",
                        help="Initialize Postgres schema only")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be created")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("FAP — Folder Automations & Pipelines")
    logger.info("=" * 60)

    if args.dry_run:
        logger.info("DRY RUN — showing planned structure:")
        for name, path in DIRS.items():
            exists = "✓" if os.path.exists(path) else "✗"
            logger.info(f"  [{exists}] {name}: {path}")
        return

    logger.info("Creating directory structure...")
    create_directories()

    engine = create_engine()

    if args.init_db:
        logger.info("Initializing Postgres schema...")
        engine.init_db()
        logger.info("Done. Schema created.")
        return

    engine.init_db()
    logger.info("Starting FAP engine...")
    engine.start()

    try:
        logger.info("FAP running. Press Ctrl+C to stop.")
        import time
        while True:
            time.sleep(60)
            engine.sweep()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        engine.stop()


if __name__ == "__main__":
    main()
