"""
llm_hub.py — AI Checkpoint Layer for FAP Pipeline.

Not every station is a dumb file-mover. Some stations THINK.
The LLM Hub manages AI processing:
  - Queue-based (not real-time watchers)
  - Supports multiple backends (Ollama local, Claude API, OpenAI)
  - Cost tracking per call
  - Prompt versioning (every prompt stored in wiki/prompts/)
  - Batch scheduling (light=15min, heavy=2x/day)

Architecture:
  Station detects file → queues to LLM Hub → Hub processes on schedule
  → Result written back → Station reads result and makes verdict
"""

import json
import os
import time
import threading
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field, asdict
from enum import Enum

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

logger = logging.getLogger("LLM-Hub")


class LLMBackend(Enum):
    OLLAMA = "ollama"           # local, fast, cheap
    CLAUDE_API = "claude_api"   # powerful, expensive, batched
    OPENAI = "openai"           # alternative
    LOCAL_EMBED = "local_embed" # sentence-transformers for vectors


class Priority(Enum):
    IMMEDIATE = "immediate"     # process now (rare)
    STANDARD = "standard"       # next scheduled run (every 15min)
    BATCH = "batch"             # 2x/day heavy processing
    LOW = "low"                 # whenever there's capacity


@dataclass
class LLMJob:
    job_id: str
    station_name: str
    file_path: str
    prompt_name: str           # references wiki/prompts/{name}.md
    backend: str               # ollama | claude_api | openai
    priority: str = "standard"
    status: str = "pending"    # pending | processing | completed | failed
    input_text: str = ""
    result: str = ""
    result_json: dict = field(default_factory=dict)
    cost_tokens: int = 0
    latency_ms: int = 0
    error: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: str = ""

    def to_dict(self):
        return asdict(self)


class LLMHub:
    """
    Central AI processing hub. Manages a job queue,
    dispatches to backends, tracks costs, logs everything.
    """

    def __init__(self, queue_dir: str = r"D:\FAP\_queue",
                 prompts_dir: str = r"D:\FAP\wiki\prompts",
                 log_dir: str = r"D:\FAP\logs"):
        self.queue_dir = Path(queue_dir)
        self.prompts_dir = Path(prompts_dir)
        self.log_dir = Path(log_dir)
        self._backends = {}
        self._running = False
        self._lock = threading.Lock()
        self._job_counter = 0

        # Create queue subdirs
        for sub in ["pending", "processing", "completed", "failed"]:
            (self.queue_dir / sub).mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # ── BACKEND HIERARCHY ─────────────────────────────────
        #
        #   Tier 1: Ollama (worker — the everyday grind)
        #     - Runs every 15 min, processes all standard jobs
        #     - Free, fast, local. Does the bulk of the work.
        #     - Classification, STT cleanup, format detection,
        #       keyword extraction, quick quality checks
        #     - If confidence < escalation_threshold → Tier 2
        #
        #   Tier 2: Claude API (executive — the hard calls)
        #     - Runs 2x/day batch, or on escalation from Tier 1
        #     - Expensive, powerful. Understands the framework.
        #     - Paper grading, cross-domain analysis, axiom mapping,
        #       gap detection, voice audit, depth work
        #     - If confidence < escalation_threshold → Tier 3
        #
        #   Tier 3: David (review queue — the final authority)
        #     - Human-in-the-loop. Gray zone items land here.
        #     - Dashboard shows pending reviews with context
        #     - David's decisions train the threshold calibration
        #
        # ──────────────────────────────────────────────────────

        self.register_backend("ollama", {
            "url": "http://localhost:11434/api/generate",
            "model": "mistral",
            "timeout": 60,
            "schedule": "standard",           # every 15 min
            "tier": 1,
            "cost_per_1k_tokens": 0.0,        # free
            "escalation_threshold": 0.55,     # below this → claude
            "escalation_target": "claude_api",
            "max_input_chars": 4000,
            "tasks": [
                "classify_document",
                "stt_cleanup",
                "format_detect",
                "keyword_extract",
                "quick_quality",
                "dedup_check",
            ],
        })
        self.register_backend("claude_api", {
            "url": "https://api.anthropic.com/v1/messages",
            "model": "claude-sonnet-4-20250514",
            "timeout": 120,
            "schedule": "batch",              # 2x/day
            "tier": 2,
            "cost_per_1k_tokens": 0.003,
            "escalation_threshold": 0.40,     # below this → David
            "escalation_target": "human_review",
            "max_input_chars": 16000,
            "tasks": [
                "grade_paper",
                "cross_domain_analysis",
                "axiom_mapping",
                "gap_detection",
                "voice_audit",
                "escalated_classification",
            ],
        })
        self.register_backend("local_embed", {
            "model": "all-MiniLM-L6-v2",
            "schedule": "standard",
            "tier": 1,
            "cost_per_1k_tokens": 0.0,
            "tasks": ["vectorize", "similarity_check"],
        })

    def register_backend(self, name: str, config: dict):
        self._backends[name] = config

    def _extract_confidence(self, result: dict) -> float:
        """Extract confidence/quality score from LLM result.
        Tries to parse JSON from result text, looks for common keys."""
        text = result.get("result", "")
        try:
            # Try JSON parse
            import re
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                parsed = json.loads(match.group())
                # Check common confidence keys
                for key in ["confidence", "quality", "overall_score", "score"]:
                    if key in parsed and isinstance(parsed[key], (int, float)):
                        return float(parsed[key])
                result["result_json"] = parsed
        except (json.JSONDecodeError, AttributeError):
            pass
        return -1.0  # -1 means couldn't extract — don't escalate

    # ── Job Queue ─────────────────────────────────────────────

    def submit(self, station_name: str, file_path: str,
               prompt_name: str, backend: str = "ollama",
               priority: str = "standard",
               input_text: str = "") -> str:
        """Submit a job to the LLM hub queue."""
        with self._lock:
            self._job_counter += 1
            job_id = f"llm_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self._job_counter:04d}"

        job = LLMJob(
            job_id=job_id,
            station_name=station_name,
            file_path=file_path,
            prompt_name=prompt_name,
            backend=backend,
            priority=priority,
            input_text=input_text[:8000],  # truncate for safety
        )

        # Write to queue
        job_file = self.queue_dir / "pending" / f"{job_id}.json"
        with open(job_file, "w") as f:
            json.dump(job.to_dict(), f, indent=2)

        logger.info(f"Queued: {job_id} [{backend}] for {station_name}")
        return job_id

    def get_pending_count(self) -> int:
        return sum(1 for _ in (self.queue_dir / "pending").glob("*.json"))

    def get_job(self, job_id: str) -> Optional[LLMJob]:
        """Check all queue subdirs for a job."""
        for sub in ["pending", "processing", "completed", "failed"]:
            path = self.queue_dir / sub / f"{job_id}.json"
            if path.exists():
                with open(path) as f:
                    data = json.load(f)
                return LLMJob(**{k: v for k, v in data.items()
                               if k in LLMJob.__dataclass_fields__})
        return None

    # ── Processing ────────────────────────────────────────────

    def process_queue(self, backend_filter: str = None,
                      priority_filter: str = None,
                      max_jobs: int = 20):
        """Process pending jobs. Called on schedule."""
        pending = self.queue_dir / "pending"
        jobs = sorted(pending.glob("*.json"), key=lambda p: p.stat().st_mtime)

        processed = 0
        for job_file in jobs:
            if processed >= max_jobs:
                break

            with open(job_file) as f:
                data = json.load(f)

            # Filter
            if backend_filter and data.get("backend") != backend_filter:
                continue
            if priority_filter and data.get("priority") != priority_filter:
                continue

            # Move to processing
            proc_file = self.queue_dir / "processing" / job_file.name
            job_file.rename(proc_file)

            # Dispatch
            result = self._dispatch(data)

            # ── ESCALATION CHECK ──────────────────────────────
            # If the result includes a confidence score below the
            # backend's escalation threshold, requeue for next tier
            if result.get("status") == "completed":
                confidence = self._extract_confidence(result)
                backend_cfg = self._backends.get(data.get("backend"), {})
                esc_threshold = backend_cfg.get("escalation_threshold", 0.0)
                esc_target = backend_cfg.get("escalation_target", "")

                if confidence > 0 and confidence < esc_threshold and esc_target:
                    tier = backend_cfg.get("tier", 0)
                    if esc_target == "human_review":
                        # Tier 3: goes to David's review queue
                        result["status"] = "review"
                        result["escalation"] = {
                            "from_backend": data.get("backend"),
                            "from_tier": tier,
                            "confidence": confidence,
                            "threshold": esc_threshold,
                            "reason": "Below confidence threshold — needs human review",
                        }
                        logger.info(
                            f"  ESCALATE → David review queue "
                            f"(confidence={confidence:.2f} < {esc_threshold})")
                    else:
                        # Re-queue for higher tier backend
                        self.submit(
                            station_name=data.get("station_name", ""),
                            file_path=data.get("file_path", ""),
                            prompt_name=data.get("prompt_name", ""),
                            backend=esc_target,
                            priority="standard",
                            input_text=data.get("input_text", ""),
                        )
                        result["escalation"] = {
                            "from_backend": data.get("backend"),
                            "to_backend": esc_target,
                            "from_tier": tier,
                            "to_tier": self._backends.get(esc_target, {}).get("tier", tier + 1),
                            "confidence": confidence,
                            "threshold": esc_threshold,
                        }
                        logger.info(
                            f"  ESCALATE → {esc_target} "
                            f"(confidence={confidence:.2f} < {esc_threshold})")

            # Update job
            data.update(result)
            data["completed_at"] = datetime.now().isoformat()

            # Move to completed or failed
            dest_dir = "completed" if data["status"] == "completed" else "failed"
            dest_file = self.queue_dir / dest_dir / proc_file.name
            with open(dest_file, "w") as f:
                json.dump(data, f, indent=2)
            if proc_file.exists():
                proc_file.unlink()

            # Log
            self._log_job(data)
            processed += 1

        logger.info(f"Processed {processed} LLM jobs")
        return processed

    def _dispatch(self, job_data: dict) -> dict:
        """Send job to the appropriate backend."""
        backend = job_data.get("backend", "ollama")
        config = self._backends.get(backend, {})

        # Load prompt template
        prompt_text = self._load_prompt(job_data.get("prompt_name", ""))
        if prompt_text:
            # Inject input text into prompt
            full_prompt = prompt_text.replace("{{INPUT}}", job_data.get("input_text", ""))
        else:
            full_prompt = job_data.get("input_text", "")

        start = time.time()

        try:
            if backend == "ollama":
                result = self._call_ollama(full_prompt, config)
            elif backend == "claude_api":
                result = self._call_claude(full_prompt, config)
            else:
                result = {"status": "failed", "error": f"Unknown backend: {backend}"}
        except Exception as e:
            result = {"status": "failed", "error": str(e)}

        result["latency_ms"] = int((time.time() - start) * 1000)
        return result

    def _call_ollama(self, prompt: str, config: dict) -> dict:
        if not HAS_REQUESTS:
            return {"status": "failed", "error": "requests not installed"}
        try:
            r = requests.post(config["url"], json={
                "model": config.get("model", "mistral"),
                "prompt": prompt,
                "stream": False,
            }, timeout=config.get("timeout", 60))
            if r.ok:
                resp = r.json().get("response", "")
                return {
                    "status": "completed",
                    "result": resp,
                    "cost_tokens": len(prompt.split()) + len(resp.split()),
                }
            return {"status": "failed", "error": f"HTTP {r.status_code}"}
        except Exception as e:
            return {"status": "failed", "error": str(e)}

    def _call_claude(self, prompt: str, config: dict) -> dict:
        if not HAS_REQUESTS:
            return {"status": "failed", "error": "requests not installed"}
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            return {"status": "failed", "error": "ANTHROPIC_API_KEY not set"}
        try:
            r = requests.post(config["url"], json={
                "model": config.get("model", "claude-sonnet-4-20250514"),
                "max_tokens": 4096,
                "messages": [{"role": "user", "content": prompt}],
            }, headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }, timeout=config.get("timeout", 120))
            if r.ok:
                data = r.json()
                text = "".join(
                    b.get("text", "") for b in data.get("content", [])
                    if b.get("type") == "text"
                )
                usage = data.get("usage", {})
                return {
                    "status": "completed",
                    "result": text,
                    "cost_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
                }
            return {"status": "failed", "error": f"HTTP {r.status_code}: {r.text[:200]}"}
        except Exception as e:
            return {"status": "failed", "error": str(e)}

    # ── Prompts ───────────────────────────────────────────────

    def _load_prompt(self, prompt_name: str) -> Optional[str]:
        if not prompt_name:
            return None
        path = self.prompts_dir / f"{prompt_name}.md"
        if path.exists():
            return path.read_text(encoding="utf-8")
        return None

    # ── Logging ───────────────────────────────────────────────

    def _log_job(self, job_data: dict):
        log_file = self.log_dir / "llm_jobs.jsonl"
        with open(log_file, "a") as f:
            f.write(json.dumps({
                "job_id": job_data.get("job_id"),
                "station": job_data.get("station_name"),
                "backend": job_data.get("backend"),
                "status": job_data.get("status"),
                "cost_tokens": job_data.get("cost_tokens", 0),
                "latency_ms": job_data.get("latency_ms", 0),
                "error": job_data.get("error", ""),
                "timestamp": datetime.now().isoformat(),
            }) + "\n")

    # ── Wiki Integration ──────────────────────────────────────

    def update_wiki_page(self, station_name: str, stats: dict):
        """Auto-update a station's wiki page with latest stats."""
        wiki_dir = Path(r"D:\FAP\wiki\stations")
        wiki_dir.mkdir(parents=True, exist_ok=True)
        page = wiki_dir / f"{station_name}.md"

        content = f"""# Station: {station_name}
*Auto-updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*

## Current Stats
| Metric | Value |
|--------|-------|
| Total processed | {stats.get('total_processed', 0)} |
| Pass rate | {stats.get('pass_rate', 0):.1%} |
| Avg score | {stats.get('avg_score', 0):.2f} |
| Avg latency | {stats.get('avg_latency_ms', 0):.0f}ms |
| LLM calls | {stats.get('llm_calls', 0)} |
| Total tokens | {stats.get('total_tokens', 0)} |

## Recent Activity
{stats.get('recent_activity', '_No activity yet._')}

## Configuration
- Input: `{stats.get('input_dir', 'N/A')}`
- Output: `{stats.get('output_dir', 'N/A')}`
- Pass threshold: {stats.get('threshold_pass', 0.7)}
- Fail threshold: {stats.get('threshold_fail', 0.3)}
- Backend: {stats.get('backend', 'ollama')}

## Prompt
Uses: `wiki/prompts/{stats.get('prompt_name', station_name)}.md`

## Error Log
{stats.get('error_log', '_No errors._')}
"""
        page.write_text(content, encoding="utf-8")
        logger.info(f"Wiki updated: {page}")

    # ── Scheduling ────────────────────────────────────────────

    def start_scheduler(self, interval_standard: int = 900,
                        interval_batch: int = 43200):
        """Start background scheduler threads."""
        self._running = True

        def standard_loop():
            while self._running:
                try:
                    self.process_queue(priority_filter="standard", max_jobs=10)
                    self.process_queue(priority_filter="immediate", max_jobs=5)
                except Exception as e:
                    logger.error(f"Standard loop error: {e}")
                time.sleep(interval_standard)

        def batch_loop():
            while self._running:
                try:
                    self.process_queue(backend_filter="claude_api", max_jobs=50)
                except Exception as e:
                    logger.error(f"Batch loop error: {e}")
                time.sleep(interval_batch)

        t1 = threading.Thread(target=standard_loop, daemon=True, name="llm-standard")
        t2 = threading.Thread(target=batch_loop, daemon=True, name="llm-batch")
        t1.start()
        t2.start()
        logger.info(f"LLM Hub scheduler started (standard={interval_standard}s, batch={interval_batch}s)")

    def stop(self):
        self._running = False
