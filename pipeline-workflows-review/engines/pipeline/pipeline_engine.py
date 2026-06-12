"""
pipeline_engine.py — The nervous system.

Manages station registry, file watchers, manifest tracking,
signal routing, and Postgres logging. Plugs into PIL/BIL.

Architecture:
  - Stations register themselves with the engine
  - Engine watches all station input dirs via watchdog
  - When a file lands, engine looks up the station, fires process()
  - Based on verdict, routes file to next station or rejection
  - Every action logged to Postgres (fap_manifests, fap_actions)
  - Signals from stations get routed to dashboard / comms
"""

import os
import json
import shutil
import threading
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import asdict

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileCreatedEvent
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False
    class FileSystemEventHandler:
        pass

    class FileCreatedEvent:
        pass

    class Observer:
        pass

try:
    import psycopg2
    import psycopg2.extras
    HAS_PG = True
except ImportError:
    HAS_PG = False

from .station_base import (
    StationBase, StationVerdict, Manifest, Signal, SignalType
)

logger = logging.getLogger("FAP")
logger.setLevel(logging.INFO)


# ══════════════════════════════════════════════════════════════════
# POSTGRES DDL — run once to set up tables
# ══════════════════════════════════════════════════════════════════
DDL = """
CREATE SCHEMA IF NOT EXISTS fap;

CREATE TABLE IF NOT EXISTS fap.stations (
    name            TEXT PRIMARY KEY,
    input_dir       TEXT NOT NULL,
    output_dir      TEXT NOT NULL,
    fail_dir        TEXT,
    review_dir      TEXT,
    threshold_pass  REAL DEFAULT 0.7,
    threshold_fail  REAL DEFAULT 0.3,
    file_extensions TEXT[] DEFAULT '{*}',
    pipeline_name   TEXT,
    station_order   INT DEFAULT 0,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fap.manifests (
    id              SERIAL PRIMARY KEY,
    file_hash       TEXT NOT NULL,
    file_path       TEXT NOT NULL,
    pipeline_name   TEXT NOT NULL,
    current_station TEXT NOT NULL,
    status          TEXT DEFAULT 'active',
    scores          JSONB DEFAULT '{}',
    metadata        JSONB DEFAULT '{}',
    history         JSONB DEFAULT '[]',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fap.actions (
    id              SERIAL PRIMARY KEY,
    manifest_id     INT REFERENCES fap.manifests(id),
    station_name    TEXT NOT NULL,
    action          TEXT NOT NULL,
    verdict         TEXT,
    score           REAL,
    notes           TEXT,
    file_from       TEXT,
    file_to         TEXT,
    timestamp       TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fap.signals (
    id              SERIAL PRIMARY KEY,
    signal_type     TEXT NOT NULL,
    source_station  TEXT NOT NULL,
    message         TEXT NOT NULL,
    payload         JSONB DEFAULT '{}',
    acknowledged    BOOLEAN DEFAULT FALSE,
    timestamp       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_manifests_hash ON fap.manifests(file_hash);
CREATE INDEX IF NOT EXISTS idx_manifests_status ON fap.manifests(status);
CREATE INDEX IF NOT EXISTS idx_actions_manifest ON fap.actions(manifest_id);
CREATE INDEX IF NOT EXISTS idx_signals_unack ON fap.signals(acknowledged) WHERE NOT acknowledged;
"""


# ══════════════════════════════════════════════════════════════════
# FILE WATCHER — watches all registered hot folders
# ══════════════════════════════════════════════════════════════════
class StationFileHandler(FileSystemEventHandler):
    """Handles file creation events in watched station folders."""

    def __init__(self, engine: "PipelineEngine", station: StationBase):
        self.engine = engine
        self.station = station
        self._debounce = {}
        self._lock = threading.Lock()

    def on_created(self, event):
        if event.is_directory:
            return
        fp = Path(event.src_path)
        # Skip temp files, partials, system files
        if fp.name.startswith((".", "~", "_")) or fp.suffix in [".tmp", ".crdownload"]:
            return
        if not self.station.accepts_file(fp):
            return
        # Debounce: wait 2s for file to finish writing
        with self._lock:
            self._debounce[str(fp)] = time.time()
        threading.Timer(2.0, self._process_if_stable, args=[fp]).start()

    def _process_if_stable(self, fp: Path):
        with self._lock:
            last = self._debounce.get(str(fp), 0)
            if time.time() - last < 1.8:
                return  # still being written
            self._debounce.pop(str(fp), None)
        if fp.exists():
            self.engine._handle_file(self.station, fp)


# ══════════════════════════════════════════════════════════════════
# PIPELINE ENGINE — the core
# ══════════════════════════════════════════════════════════════════
class PipelineEngine:
    """
    The FAP nervous system. Manages stations, watches folders,
    routes files, logs everything.
    """

    def __init__(self, pg_dsn: str = None, log_dir: str = None):
        self.stations: dict[str, StationBase] = {}
        self.pipelines: dict[str, list[str]] = {}  # pipeline_name -> [station_names in order]
        self.observer = Observer() if HAS_WATCHDOG else None
        self.pg_dsn = pg_dsn or os.environ.get(
            "FAP_PG_DSN",
            "",
        )
        self.log_dir = Path(log_dir or os.environ.get("FAP_LOG_DIR", r"D:\BIL\data\fap_logs"))
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._conn = None
        self._signal_handlers: list[callable] = []
        self._running = False

    # ── Postgres ──────────────────────────────────────────────────

    def _get_conn(self):
        if not HAS_PG or not self.pg_dsn:
            return None
        if self._conn is None or self._conn.closed:
            try:
                self._conn = psycopg2.connect(self.pg_dsn)
                self._conn.autocommit = True
            except Exception as e:
                logger.warning(f"Postgres unavailable: {e}")
                self._conn = None
        return self._conn

    def init_db(self):
        conn = self._get_conn()
        if conn:
            with conn.cursor() as cur:
                cur.execute(DDL)
            logger.info("FAP schema initialized in Postgres")

    def _log_to_pg(self, table: str, data: dict):
        conn = self._get_conn()
        if not conn:
            # Fallback: log to local JSONL
            log_file = self.log_dir / f"{table}.jsonl"
            with open(log_file, "a") as f:
                f.write(json.dumps(data, default=str) + "\n")
            return None
        cols = ", ".join(data.keys())
        placeholders = ", ".join(["%s"] * len(data))
        sql = f"INSERT INTO fap.{table} ({cols}) VALUES ({placeholders}) RETURNING id"
        try:
            with conn.cursor() as cur:
                cur.execute(sql, list(data.values()))
                row = cur.fetchone()
                return row[0] if row else None
        except Exception as e:
            logger.error(f"PG insert failed: {e}")
            return None

    # ── Station Management ────────────────────────────────────────

    def register_station(self, station: StationBase, pipeline_name: str = "default",
                         order: int = 0):
        self.stations[station.name] = station
        if pipeline_name not in self.pipelines:
            self.pipelines[pipeline_name] = []
        if station.name not in self.pipelines[pipeline_name]:
            self.pipelines[pipeline_name].append(station.name)
            # Sort by order
            self.pipelines[pipeline_name].sort(
                key=lambda n: self._get_station_order(n, pipeline_name))

        # Log to PG
        self._log_to_pg("stations", {
            "name": station.name,
            "input_dir": str(station.input_dir),
            "output_dir": str(station.output_dir),
            "fail_dir": str(station.fail_dir),
            "review_dir": str(station.review_dir),
            "threshold_pass": station.threshold_pass,
            "threshold_fail": station.threshold_fail,
            "pipeline_name": pipeline_name,
            "station_order": order,
        })

        # Set up watcher
        if self.observer and station.input_dir.exists():
            handler = StationFileHandler(self, station)
            self.observer.schedule(handler, str(station.input_dir), recursive=False)
            logger.info(f"Watching: {station.input_dir} -> Station:{station.name}")

    def _get_station_order(self, station_name: str, pipeline_name: str) -> int:
        # Could look up from PG, for now use registration order
        return self.pipelines.get(pipeline_name, []).index(station_name)

    def get_next_station(self, current_station: str, pipeline_name: str) -> Optional[str]:
        pipeline = self.pipelines.get(pipeline_name, [])
        try:
            idx = pipeline.index(current_station)
            if idx + 1 < len(pipeline):
                return pipeline[idx + 1]
        except ValueError:
            pass
        return None

    # ── Signal Handling ───────────────────────────────────────────

    def on_signal(self, handler: callable):
        self._signal_handlers.append(handler)

    def _route_signals(self, station: StationBase):
        for sig in station.drain_signals():
            # Log to PG
            self._log_to_pg("signals", sig.to_dict())
            # Notify handlers
            for handler in self._signal_handlers:
                try:
                    handler(sig)
                except Exception as e:
                    logger.error(f"Signal handler error: {e}")
            logger.info(f"SIGNAL [{sig.signal_type.value}] from {sig.source_station}: {sig.message}")

    # ── File Processing ───────────────────────────────────────────

    def _handle_file(self, station: StationBase, file_path: Path):
        logger.info(f"Processing: {file_path.name} at Station:{station.name}")

        # Create or load manifest
        file_hash = Manifest.compute_hash(str(file_path))
        manifest = Manifest(
            file_path=str(file_path),
            file_hash=file_hash,
            pipeline_name=self._get_pipeline_for_station(station.name),
            current_station=station.name,
        )

        # Run the station's processor
        try:
            verdict, score, notes = station.process(file_path, manifest)
        except Exception as e:
            verdict = StationVerdict.FAIL
            score = 0.0
            notes = f"Processing error: {e}"
            logger.error(f"Station {station.name} error on {file_path}: {e}")

        # Record in manifest
        manifest.record_station(station.name, verdict, score, notes)

        # Route based on verdict
        dest = None
        if verdict == StationVerdict.PASS:
            next_station = self.get_next_station(station.name, manifest.pipeline_name)
            if next_station and next_station in self.stations:
                dest = self.stations[next_station].input_dir
                manifest.current_station = next_station
            else:
                dest = station.output_dir
                manifest.status = "completed"
                station.emit_signal(SignalType.READY,
                    f"{file_path.name} completed pipeline {manifest.pipeline_name}")
        elif verdict == StationVerdict.FAIL:
            dest = station.fail_dir
            manifest.status = "failed"
        elif verdict == StationVerdict.REVIEW:
            dest = station.review_dir
            manifest.status = "review"
        elif verdict == StationVerdict.LOOP:
            # notes should contain target station name
            target = notes.split("->")[-1].strip() if "->" in notes else station.name
            if target in self.stations:
                dest = self.stations[target].input_dir
                manifest.current_station = target
            else:
                dest = station.review_dir
                manifest.status = "review"
        elif verdict == StationVerdict.HOLD:
            dest = None  # stays in place
            manifest.status = "hold"

        # Move file
        if dest and dest != file_path.parent:
            dest.mkdir(parents=True, exist_ok=True)
            new_path = dest / file_path.name
            # Handle name conflicts
            if new_path.exists():
                stem = file_path.stem
                suffix = file_path.suffix
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                new_path = dest / f"{stem}_{ts}{suffix}"
            shutil.move(str(file_path), str(new_path))
            manifest.file_path = str(new_path)

        # Log action to PG
        manifest_id = self._log_to_pg("manifests", {
            "file_hash": manifest.file_hash,
            "file_path": manifest.file_path,
            "pipeline_name": manifest.pipeline_name,
            "current_station": manifest.current_station,
            "status": manifest.status,
            "scores": json.dumps(manifest.scores),
            "metadata": json.dumps(manifest.metadata),
            "history": json.dumps(manifest.history),
        })

        self._log_to_pg("actions", {
            "manifest_id": manifest_id,
            "station_name": station.name,
            "action": "process",
            "verdict": verdict.value,
            "score": score,
            "notes": notes,
            "file_from": str(file_path),
            "file_to": manifest.file_path,
        })

        # Route any signals the station emitted
        self._route_signals(station)

        logger.info(f"  -> {verdict.value} (score={score:.2f}) -> {dest or 'HOLD'}")

    def _get_pipeline_for_station(self, station_name: str) -> str:
        for pname, stations in self.pipelines.items():
            if station_name in stations:
                return pname
        return "default"

    # ── Sweep (cold folders) ──────────────────────────────────────

    def sweep(self, station_name: str = None):
        """Manually sweep a station's input dir, or all stations."""
        targets = [station_name] if station_name else list(self.stations.keys())
        for name in targets:
            station = self.stations.get(name)
            if not station:
                continue
            for fp in station.input_dir.iterdir():
                if fp.is_file() and not fp.name.startswith((".", "_")):
                    if station.accepts_file(fp):
                        self._handle_file(station, fp)

    # ── Lifecycle ─────────────────────────────────────────────────

    def start(self):
        if self.observer:
            self.observer.start()
            self._running = True
            logger.info(f"FAP Engine started — watching {len(self.stations)} stations")

    def stop(self):
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self._running = False
            logger.info("FAP Engine stopped")

    def is_running(self) -> bool:
        return self._running

    # ── Status / Dashboard Data ───────────────────────────────────

    def get_status(self) -> dict:
        """Returns full engine status for dashboard rendering."""
        station_status = {}
        for name, station in self.stations.items():
            input_count = sum(1 for f in station.input_dir.iterdir()
                            if f.is_file() and not f.name.startswith("."))
            station_status[name] = {
                "input_dir": str(station.input_dir),
                "output_dir": str(station.output_dir),
                "pending_files": input_count,
                "threshold_pass": station.threshold_pass,
                "threshold_fail": station.threshold_fail,
                "pipeline": self._get_pipeline_for_station(name),
            }

        return {
            "running": self._running,
            "station_count": len(self.stations),
            "pipelines": {k: v for k, v in self.pipelines.items()},
            "stations": station_status,
            "timestamp": datetime.now().isoformat(),
        }
