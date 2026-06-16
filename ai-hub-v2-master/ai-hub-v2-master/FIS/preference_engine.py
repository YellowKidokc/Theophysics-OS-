"""Preference Engine — Markov chains + transition matrices that learn from decisions.

Architecture:
  - Markov chain: P(domain | keywords, extension, context) 
  - Transition matrix: tracks domain→domain corrections (what you change TO)
  - Decision log: every approve/reject/override feeds the chain
  - Prediction: weighted vote across keyword chains + extension priors + correction history

The loop:
  classify → predict → user votes → engine learns → predictions improve → eventually auto-approve
"""

import json
import os
import sqlite3
import time
from collections import defaultdict
from pathlib import Path
from typing import Optional

DEFAULT_DB_DIR = Path(r"\\192.168.2.50\brain\09_DATABASES\FIS")
DB_DIR = Path(os.environ.get("FIS_DATABASE_DIR", DEFAULT_DB_DIR))
DB_PATH = DB_DIR / "preference_engine.db"


def ensure_database_dir() -> None:
    DB_DIR.mkdir(parents=True, exist_ok=True)


def get_db() -> sqlite3.Connection:
    """Initialize preference engine database."""
    ensure_database_dir()
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    
    # Decision log — every approve/reject/override
    conn.execute('''CREATE TABLE IF NOT EXISTS decisions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT,
        extension TEXT,
        keywords TEXT,           -- JSON array of top keywords
        proposed_domain TEXT,    -- what the classifier said
        final_domain TEXT,       -- what the user approved (may differ)
        confidence REAL,         -- classifier confidence
        action TEXT,             -- approve | reject | override
        source TEXT,             -- yake | deberta | ollama | markov
        timestamp REAL
    )''')
    
    # Keyword → domain transition counts (the Markov chain)
    conn.execute('''CREATE TABLE IF NOT EXISTS keyword_chains (
        keyword TEXT,
        domain TEXT,
        count INTEGER DEFAULT 0,
        last_seen REAL,
        PRIMARY KEY (keyword, domain)
    )''')
    
    # Extension → domain transition counts
    conn.execute('''CREATE TABLE IF NOT EXISTS ext_chains (
        extension TEXT,
        domain TEXT,
        count INTEGER DEFAULT 0,
        PRIMARY KEY (extension, domain)
    )''')
    
    # Domain correction matrix: proposed → corrected
    conn.execute('''CREATE TABLE IF NOT EXISTS correction_matrix (
        from_domain TEXT,
        to_domain TEXT,
        count INTEGER DEFAULT 0,
        PRIMARY KEY (from_domain, to_domain)
    )''')
    
    # Aggregate stats for auto-approve threshold
    conn.execute('''CREATE TABLE IF NOT EXISTS engine_stats (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')
    
    conn.commit()
    return conn


def record_decision(filename: str, extension: str, keywords: list,
                    proposed_domain: str, final_domain: str,
                    confidence: float, action: str, source: str = "yake"):
    """Record a user decision and update all chains."""
    conn = get_db()
    now = time.time()
    
    # 1. Log the decision
    conn.execute(
        '''INSERT INTO decisions 
           (filename, extension, keywords, proposed_domain, final_domain,
            confidence, action, source, timestamp)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (filename, extension, json.dumps(keywords), proposed_domain,
         final_domain, confidence, action, source, now)
    )
    
    # 2. Update keyword chains — each keyword votes for the final domain
    for kw in keywords:
        kw_lower = kw.lower().strip()
        if len(kw_lower) < 2:
            continue
        conn.execute(
            '''INSERT INTO keyword_chains (keyword, domain, count, last_seen)
               VALUES (?, ?, 1, ?)
               ON CONFLICT(keyword, domain) 
               DO UPDATE SET count = count + 1, last_seen = ?''',
            (kw_lower, final_domain, now, now)
        )
    
    # 3. Update extension chain
    if extension:
        conn.execute(
            '''INSERT INTO ext_chains (extension, domain, count)
               VALUES (?, ?, 1)
               ON CONFLICT(extension, domain) 
               DO UPDATE SET count = count + 1''',
            (extension.lower(), final_domain)
        )
    
    # 4. Update correction matrix (if user overrode)
    if action == "override" and proposed_domain != final_domain:
        conn.execute(
            '''INSERT INTO correction_matrix (from_domain, to_domain, count)
               VALUES (?, ?, 1)
               ON CONFLICT(from_domain, to_domain) 
               DO UPDATE SET count = count + 1''',
            (proposed_domain, final_domain)
        )
    
    conn.commit()
    conn.close()


def predict_domain(keywords: list, extension: str) -> Optional[dict]:
    """Use learned chains to predict domain classification.
    
    Returns dict with:
      domain: predicted domain
      confidence: 0-100
      keyword_votes: {domain: vote_count}
      ext_signal: {domain: count} from extension history
      correction_warning: if this domain is frequently overridden
    """
    conn = get_db()
    
    # Check if we have enough data to predict
    total_decisions = conn.execute(
        "SELECT COUNT(*) FROM decisions"
    ).fetchone()[0]
    
    if total_decisions < 5:
        conn.close()
        return None  # Not enough training data yet
    
    # 1. Keyword chain votes
    keyword_votes = defaultdict(float)
    for kw in keywords:
        kw_lower = kw.lower().strip()
        rows = conn.execute(
            "SELECT domain, count FROM keyword_chains WHERE keyword = ?",
            (kw_lower,)
        ).fetchall()
        total = sum(r[1] for r in rows) or 1
        for domain, count in rows:
            keyword_votes[domain] += count / total  # Normalized vote
    
    # 2. Extension signal
    ext_signal = {}
    if extension:
        rows = conn.execute(
            "SELECT domain, count FROM ext_chains WHERE extension = ?",
            (extension.lower(),)
        ).fetchall()
        total = sum(r[1] for r in rows) or 1
        ext_signal = {d: c / total for d, c in rows}
    
    # 3. Combined score: keywords (60%) + extension (40%)
    combined = defaultdict(float)
    for d, v in keyword_votes.items():
        combined[d] += v * 0.6
    for d, v in ext_signal.items():
        combined[d] += v * 0.4
    
    if not combined:
        conn.close()
        return None
    
    # Best prediction
    best_domain = max(combined, key=combined.get)
    total_score = sum(combined.values()) or 1
    raw_confidence = combined[best_domain] / total_score * 100
    
    # 4. Check correction history — does this domain get overridden often?
    corrections = conn.execute(
        "SELECT to_domain, count FROM correction_matrix WHERE from_domain = ?",
        (best_domain,)
    ).fetchall()
    
    correction_warning = None
    if corrections:
        total_corrections = sum(c[1] for c in corrections)
        approvals = conn.execute(
            "SELECT COUNT(*) FROM decisions WHERE proposed_domain = ? AND action = 'approve'",
            (best_domain,)
        ).fetchone()[0]
        
        if approvals + total_corrections > 0:
            override_rate = total_corrections / (approvals + total_corrections)
            if override_rate > 0.3:
                top_correction = max(corrections, key=lambda x: x[1])
                correction_warning = {
                    "override_rate": round(override_rate * 100, 1),
                    "usually_corrected_to": top_correction[0],
                    "correction_count": top_correction[1],
                }
                # Adjust confidence down
                raw_confidence *= (1 - override_rate * 0.5)
    
    conn.close()
    
    return {
        "domain": best_domain,
        "confidence": round(min(raw_confidence, 99), 1),
        "keyword_votes": dict(keyword_votes),
        "ext_signal": ext_signal,
        "correction_warning": correction_warning,
        "source": "markov",
        "training_size": total_decisions,
    }


def get_auto_approve_threshold() -> float:
    """Calculate dynamic auto-approve threshold based on accuracy history.
    
    Starts conservative (90%), drops as accuracy improves.
    """
    conn = get_db()
    
    # How often do our predictions match user decisions?
    total = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
    if total < 20:
        conn.close()
        return 95.0  # Very conservative until we have data
    
    correct = conn.execute(
        "SELECT COUNT(*) FROM decisions WHERE proposed_domain = final_domain"
    ).fetchone()[0]
    
    accuracy = correct / total * 100 if total > 0 else 0
    conn.close()
    
    # Scale threshold inversely with accuracy
    # 95% accuracy → 70% threshold (aggressive auto-approve)
    # 80% accuracy → 85% threshold (moderate)
    # 60% accuracy → 95% threshold (conservative)
    if accuracy >= 95:
        return 70.0
    elif accuracy >= 90:
        return 75.0
    elif accuracy >= 85:
        return 80.0
    elif accuracy >= 80:
        return 85.0
    else:
        return 95.0


def get_engine_stats() -> dict:
    """Get current engine performance statistics."""
    conn = get_db()
    
    total = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
    approvals = conn.execute(
        "SELECT COUNT(*) FROM decisions WHERE action = 'approve'"
    ).fetchone()[0]
    overrides = conn.execute(
        "SELECT COUNT(*) FROM decisions WHERE action = 'override'"
    ).fetchone()[0]
    rejects = conn.execute(
        "SELECT COUNT(*) FROM decisions WHERE action = 'reject'"
    ).fetchone()[0]
    
    unique_keywords = conn.execute(
        "SELECT COUNT(DISTINCT keyword) FROM keyword_chains"
    ).fetchone()[0]
    
    accuracy = 0
    if total > 0:
        correct = conn.execute(
            "SELECT COUNT(*) FROM decisions WHERE proposed_domain = final_domain"
        ).fetchone()[0]
        accuracy = round(correct / total * 100, 1)
    
    # Top correction patterns
    top_corrections = conn.execute(
        """SELECT from_domain, to_domain, count 
           FROM correction_matrix 
           ORDER BY count DESC LIMIT 5"""
    ).fetchall()
    
    conn.close()
    
    return {
        "database": str(DB_PATH),
        "total_decisions": total,
        "approvals": approvals,
        "overrides": overrides,
        "rejects": rejects,
        "accuracy": accuracy,
        "unique_keywords_learned": unique_keywords,
        "auto_approve_threshold": get_auto_approve_threshold(),
        "top_corrections": [
            {"from": r[0], "to": r[1], "count": r[2]}
            for r in top_corrections
        ],
    }


def batch_predict(file_results: list) -> list:
    """Run Markov prediction on a batch of classified files.
    
    Takes output from auto_sort.classify_directory, adds Markov predictions.
    """
    enhanced = []
    for r in file_results:
        keywords = [k['keyword'] for k in r.get('keywords', [])]
        ext = r.get('ext', '')
        
        markov = predict_domain(keywords, ext)
        r['markov_prediction'] = markov
        
        # If Markov disagrees with Tier 1 AND has higher confidence, flag it
        if markov and markov['confidence'] > r['classification']['confidence']:
            r['prediction_conflict'] = {
                'tier1_says': r['classification']['domain'],
                'markov_says': markov['domain'],
                'markov_confidence': markov['confidence'],
                'recommendation': markov['domain'],
            }
        
        enhanced.append(r)
    
    return enhanced
