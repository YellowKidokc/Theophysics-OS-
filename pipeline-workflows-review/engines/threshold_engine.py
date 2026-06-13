"""
threshold_engine.py
PIL Confidence Threshold — the gatekeeper.

Nothing auto-progresses without passing threshold.
Nothing auto-reverts without failing it.
Everything in between gets kicked to David.

Flow:
  1. Event arrives (capture, inbox file, clip, github)
  2. Ollama scores confidence (0.0 - 1.0)
  3. Above auto_progress_above → auto-process
  4. Below kick_to_human_below → queue for David + reminder
  5. Gray zone → Ollama second pass with more context
  6. If David doesn't resolve in auto_revert_hours → discard/revert

The threshold ADAPTS:
  - First 14 days (training_period): floor is LOW, most things kick to human
  - After min_ratings_before_auto ratings: system starts auto-processing
  - Threshold rises as confidence in scoring improves
"""

import json
import os
import time
import threading
from datetime import datetime, timedelta

# ── Review Queue ──────────────────────────────────────────────────────────────

BIL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BIL_ROOT, "bil_config.json")
DATA_DIR = os.path.join(BIL_ROOT, "data")
REVIEW_QUEUE_PATH = os.path.join(DATA_DIR, "review_queue.jsonl")
REVIEW_RESOLVED_PATH = os.path.join(DATA_DIR, "review_resolved.jsonl")

os.makedirs(DATA_DIR, exist_ok=True)


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def count_ratings():
    """Count total explicit ratings David has given."""
    path = os.path.join(DATA_DIR, "ratings", "ratings.jsonl")
    if not os.path.exists(path):
        return 0
    with open(path) as f:
        return sum(1 for _ in f)


def get_adaptive_threshold(cfg):
    """
    Returns current effective threshold based on training state.
    
    Early (< min_ratings): threshold is LOW → most things get kicked to human
    Mature (> min_ratings): threshold rises toward ceiling
    """
    t = cfg.get("threshold", {})
    floor = t.get("confidence_floor", 0.3)
    ceiling = t.get("confidence_ceiling", 0.85)
    min_ratings = t.get("min_ratings_before_auto", 50)
    
    n_ratings = count_ratings()
    
    if n_ratings < min_ratings:
        # Training period: stay near floor
        # Linear interpolation from floor toward midpoint
        progress = n_ratings / min_ratings
        midpoint = (floor + ceiling) / 2
        return floor + (midpoint - floor) * progress
    else:
        # Mature: use configured auto_progress threshold
        return t.get("auto_progress_above", 0.7)


def score_event(event, cfg):
    """
    Ask Ollama to score confidence on what this event IS and whether it's useful.
    Returns float 0.0 - 1.0
    """
    import requests
    
    description = event.get("description", "")
    event_type = event.get("type", "unknown")
    
    if not description or description == "Screenshot captured":
        return 0.1  # No description = low confidence
    
    prompt = f"""Score your confidence in understanding this {event_type} on a scale of 0.0 to 1.0.
    
Description: {description}
Type: {event_type}

Consider:
- Can you clearly identify what app/content this is? 
- Is this meaningful activity or just noise (idle screen, screensaver, lock screen)?
- Would this be useful for learning user preferences?

Reply with ONLY a number between 0.0 and 1.0, nothing else."""
    
    try:
        r = requests.post(cfg["ollama_url"], json={
            "model": "mistral",  # Use reasoning model, not vision model
            "prompt": prompt,
            "stream": False,
        }, timeout=15)
        if r.ok:
            text = r.json().get("response", "").strip()
            # Extract first float from response
            for token in text.split():
                try:
                    score = float(token.strip(".,;:"))
                    if 0.0 <= score <= 1.0:
                        return score
                except ValueError:
                    continue
    except Exception as e:
        print(f"  Threshold scoring error: {e}")
    
    return 0.5  # Default: gray zone


def second_pass(event, cfg):
    """
    Ollama gets a second look with more context.
    Used for gray-zone events that didn't clearly pass or fail.
    """
    import requests
    
    description = event.get("description", "")
    
    # Pull recent context from watcher log
    context_lines = []
    watcher_log = os.path.join(DATA_DIR, "digests", "watcher.jsonl")
    if os.path.exists(watcher_log):
        with open(watcher_log) as f:
            lines = f.readlines()
            for line in lines[-5:]:  # last 5 entries
                try:
                    entry = json.loads(line)
                    context_lines.append(entry.get("description", ""))
                except:
                    pass
    
    context = " | ".join(context_lines) if context_lines else "no recent context"
    
    prompt = f"""Score your confidence again with additional context.

Current event: {description}
Recent activity: {context}
Event type: {event.get('type', 'unknown')}

With this context, how confident are you that this event is:
1. Clearly identifiable (what is it?)
2. Meaningful (not noise)
3. Useful for preference learning

Reply with ONLY a number between 0.0 and 1.0."""
    
    try:
        r = requests.post(cfg["ollama_url"], json={
            "model": "mistral",
            "prompt": prompt,
            "stream": False,
        }, timeout=15)
        if r.ok:
            text = r.json().get("response", "").strip()
            for token in text.split():
                try:
                    score = float(token.strip(".,;:"))
                    if 0.0 <= score <= 1.0:
                        return score
                except ValueError:
                    continue
    except Exception:
        pass
    
    return 0.5


# ── Decision Engine ───────────────────────────────────────────────────────────

class ThresholdDecision:
    AUTO_PROCESS = "auto_process"
    KICK_TO_HUMAN = "kick_to_human"
    DISCARD = "discard"


def decide(event, cfg=None):
    """
    Main decision function. Returns (decision, confidence, reason).
    
    This is the gatekeeper. Nothing moves forward without passing through here.
    """
    if cfg is None:
        cfg = load_config()
    
    t = cfg.get("threshold", {})
    kick_below = t.get("kick_to_human_below", 0.4)
    auto_above = get_adaptive_threshold(cfg)
    
    # First pass
    score = score_event(event, cfg)
    
    if score >= auto_above:
        return ThresholdDecision.AUTO_PROCESS, score, "Above threshold — auto-processing"
    
    if score < 0.15:
        return ThresholdDecision.DISCARD, score, "Noise — discarding (lock screen, idle, etc.)"
    
    if score < kick_below:
        # Below threshold — kick to human
        add_to_review_queue(event, score, "Below confidence threshold")
        return ThresholdDecision.KICK_TO_HUMAN, score, "Below threshold — queued for review"
    
    # Gray zone — second pass
    score2 = second_pass(event, cfg)
    avg_score = (score + score2) / 2
    
    if avg_score >= auto_above:
        return ThresholdDecision.AUTO_PROCESS, avg_score, "Passed on second look"
    
    if avg_score < kick_below:
        add_to_review_queue(event, avg_score, "Failed second pass")
        return ThresholdDecision.KICK_TO_HUMAN, avg_score, "Failed second pass — queued"
    
    # Still gray — kick to human with note
    add_to_review_queue(event, avg_score, "Gray zone after two passes")
    return ThresholdDecision.KICK_TO_HUMAN, avg_score, "Gray zone — needs human judgment"


# ── Review Queue Management ──────────────────────────────────────────────────

def add_to_review_queue(event, confidence, reason):
    """Add event to review queue. David gets reminded until resolved."""
    entry = {
        "id": f"review_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "event": event,
        "confidence": confidence,
        "reason": reason,
        "queued_at": datetime.now().isoformat(),
        "reminder_count": 0,
        "resolved": False,
    }
    with open(REVIEW_QUEUE_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")
    print(f"  → Review queue: {reason} (conf={confidence:.2f})")


def get_pending_reviews():
    """Get all unresolved review items."""
    if not os.path.exists(REVIEW_QUEUE_PATH):
        return []
    
    pending = []
    with open(REVIEW_QUEUE_PATH) as f:
        for line in f:
            try:
                entry = json.loads(line)
                if not entry.get("resolved", False):
                    pending.append(entry)
            except:
                pass
    return pending


def resolve_review(review_id, decision, note=""):
    """Mark a review item as resolved."""
    # Read all, mark resolved, rewrite
    entries = []
    with open(REVIEW_QUEUE_PATH) as f:
        for line in f:
            try:
                entry = json.loads(line)
                if entry.get("id") == review_id:
                    entry["resolved"] = True
                    entry["resolved_at"] = datetime.now().isoformat()
                    entry["resolution"] = decision
                    entry["resolution_note"] = note
                    # Also log to resolved file
                    with open(REVIEW_RESOLVED_PATH, "a") as rf:
                        rf.write(json.dumps(entry) + "\n")
                entries.append(entry)
            except:
                pass
    
    with open(REVIEW_QUEUE_PATH, "w") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")


def auto_revert_stale(cfg=None):
    """Auto-revert items that David hasn't resolved in time."""
    if cfg is None:
        cfg = load_config()
    
    t = cfg.get("threshold", {})
    max_hours = t.get("auto_revert_hours", 24)
    cutoff = datetime.now() - timedelta(hours=max_hours)
    
    entries = []
    reverted = 0
    with open(REVIEW_QUEUE_PATH) as f:
        for line in f:
            try:
                entry = json.loads(line)
                if not entry.get("resolved", False):
                    queued = datetime.fromisoformat(entry["queued_at"])
                    if queued < cutoff:
                        entry["resolved"] = True
                        entry["resolved_at"] = datetime.now().isoformat()
                        entry["resolution"] = "auto_reverted"
                        entry["resolution_note"] = f"Stale after {max_hours}h"
                        reverted += 1
                entries.append(entry)
            except:
                pass
    
    if reverted > 0:
        with open(REVIEW_QUEUE_PATH, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")
        print(f"  Auto-reverted {reverted} stale review items")
    
    return reverted


# ── Reminder Loop ─────────────────────────────────────────────────────────────

def reminder_loop(cfg=None):
    """
    Runs in background. Checks review queue, reminds David of pending items.
    Also auto-reverts stale items.
    """
    if cfg is None:
        cfg = load_config()
    
    t = cfg.get("threshold", {})
    interval = t.get("reminder_interval_minutes", 5) * 60
    
    while True:
        try:
            pending = get_pending_reviews()
            if pending:
                print(f"\n  ⚠ {len(pending)} items awaiting review:")
                for item in pending[:5]:
                    desc = item.get("event", {}).get("description", "?")[:60]
                    conf = item.get("confidence", 0)
                    print(f"    [{item['id']}] conf={conf:.2f} — {desc}")
                
                # TODO: trigger desktop notification via pystray or toast
                # For now just console output
            
            # Auto-revert stale
            auto_revert_stale(cfg)
            
        except Exception as e:
            print(f"  Reminder error: {e}")
        
        time.sleep(interval)


# ── CLI for manual resolution ─────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("BIL Threshold Engine")
        print(f"  Adaptive threshold: {get_adaptive_threshold(load_config()):.2f}")
        print(f"  Total ratings: {count_ratings()}")
        print()
        pending = get_pending_reviews()
        if pending:
            print(f"  {len(pending)} pending reviews:")
            for item in pending:
                desc = item.get("event", {}).get("description", "?")[:60]
                conf = item.get("confidence", 0)
                age = item.get("queued_at", "?")
                print(f"    [{item['id']}] conf={conf:.2f} queued={age[:16]} — {desc}")
        else:
            print("  No pending reviews.")
        print()
        print("Commands:")
        print("  python threshold_engine.py resolve <id> keep|discard [note]")
        print("  python threshold_engine.py flush  — auto-revert all stale")
        print("  python threshold_engine.py test <text>  — score a test event")
    
    elif sys.argv[1] == "resolve" and len(sys.argv) >= 4:
        resolve_review(sys.argv[2], sys.argv[3], " ".join(sys.argv[4:]))
        print(f"  Resolved: {sys.argv[2]} → {sys.argv[3]}")
    
    elif sys.argv[1] == "flush":
        n = auto_revert_stale()
        print(f"  Flushed {n} stale items")
    
    elif sys.argv[1] == "test":
        text = " ".join(sys.argv[2:])
        event = {"type": "test", "description": text}
        decision, conf, reason = decide(event)
        print(f"  Decision: {decision}")
        print(f"  Confidence: {conf:.2f}")
        print(f"  Reason: {reason}")
