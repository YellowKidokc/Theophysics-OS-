"""Cluster Engine — unsupervised file discovery.

Instead of forcing files into predefined domains, this builds a feature
matrix from every file and lets the clusters emerge naturally.

Features per file:
  - Filename tokens (TF-IDF weighted)
  - Content keywords (YAKE)
  - Extension one-hot
  - Temporal position (creation/modification timestamps)
  - Path depth and folder context

Output: natural clusters with auto-generated names from top keywords.
"""

import hashlib
import json
import os
import re
import sqlite3
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np


def extract_filename_tokens(filename: str) -> list:
    """Split filename into meaningful tokens."""
    name = Path(filename).stem
    # Split on separators, camelCase, numbers
    tokens = re.split(r'[-_\s.]+', name)
    # Also split camelCase
    expanded = []
    for t in tokens:
        expanded.extend(re.sub(r'([a-z])([A-Z])', r'\1 \2', t).split())
    # Lowercase, filter short/stopwords
    stopwords = {'the', 'and', 'for', 'that', 'this', 'with', 'are', 'was',
                 'from', 'not', 'but', 'can', 'will', 'new', 'old', 'copy',
                 'final', 'temp', 'tmp', 'test', 'untitled', 'document'}
    return [t.lower() for t in expanded if len(t) > 2 and t.lower() not in stopwords]


def build_feature_matrix(files: list, config: dict = None) -> dict:
    """Build the feature matrix for clustering.
    
    Args:
        files: list of dicts from auto_sort.classify_directory()
        config: optional weights from .sortconfig.yaml
    
    Returns:
        dict with 'matrix' (numpy array), 'file_index', 'feature_names',
        'temporal_sessions', 'keyword_graph'
    """
    if not files:
        return None
    
    weights = {
        'filename_tokens': 0.3,
        'content_keywords': 0.4,
        'extension': 0.1,
        'temporal': 0.15,
        'path_context': 0.05,
    }
    if config and 'cluster' in config:
        weights.update(config['cluster'].get('features', {}))
    
    # ─── 1. Collect all tokens across all files ───────────────
    all_tokens = Counter()
    file_tokens = []
    for f in files:
        # Filename tokens
        fn_tokens = extract_filename_tokens(f['filename'])
        # Content keywords
        kw_tokens = [k['keyword'].lower() for k in f.get('keywords', [])]
        combined = fn_tokens + kw_tokens
        file_tokens.append(combined)
        all_tokens.update(combined)
    
    # Build vocabulary (top 200 tokens by frequency, min 2 occurrences)
    vocab = [t for t, c in all_tokens.most_common(200) if c >= 2]
    vocab_idx = {t: i for i, t in enumerate(vocab)}
    
    # ─── 2. TF-IDF matrix ────────────────────────────────────
    n_files = len(files)
    n_vocab = len(vocab)
    
    # Document frequency
    doc_freq = Counter()
    for tokens in file_tokens:
        doc_freq.update(set(tokens))
    
    # TF-IDF
    tfidf = np.zeros((n_files, n_vocab))
    for i, tokens in enumerate(file_tokens):
        tf = Counter(tokens)
        for token, count in tf.items():
            if token in vocab_idx:
                j = vocab_idx[token]
                idf = np.log(n_files / (1 + doc_freq[token]))
                tfidf[i, j] = count * idf
    
    # Normalize rows
    norms = np.linalg.norm(tfidf, axis=1, keepdims=True)
    norms[norms == 0] = 1
    tfidf = tfidf / norms
    
    # ─── 3. Extension one-hot ─────────────────────────────────
    all_exts = sorted(set(f.get('ext', '').lower() for f in files))
    ext_idx = {e: i for i, e in enumerate(all_exts)}
    ext_matrix = np.zeros((n_files, len(all_exts)))
    for i, f in enumerate(files):
        ext = f.get('ext', '').lower()
        if ext in ext_idx:
            ext_matrix[i, ext_idx[ext]] = 1.0
    
    # ─── 4. Temporal features ─────────────────────────────────
    timestamps = []
    for f in files:
        try:
            stat = os.stat(f['filepath'])
            timestamps.append(stat.st_mtime)
        except (OSError, KeyError):
            timestamps.append(0)
    
    ts_array = np.array(timestamps)
    if ts_array.max() > ts_array.min():
        ts_norm = (ts_array - ts_array.min()) / (ts_array.max() - ts_array.min())
    else:
        ts_norm = np.zeros(n_files)
    
    temporal_matrix = ts_norm.reshape(-1, 1)
    
    # ─── 5. Temporal sessions (files within 3h of each other) ─
    session_window = 3 * 3600  # 3 hours in seconds
    sorted_indices = np.argsort(ts_array)
    sessions = []
    current_session = [sorted_indices[0]] if n_files > 0 else []
    
    for idx in range(1, n_files):
        i = sorted_indices[idx]
        prev = sorted_indices[idx - 1]
        if ts_array[i] - ts_array[prev] <= session_window:
            current_session.append(i)
        else:
            if len(current_session) >= 2:
                sessions.append(current_session[:])
            current_session = [i]
    if len(current_session) >= 2:
        sessions.append(current_session[:])
    
    # Name sessions by their top keywords
    named_sessions = []
    for session_indices in sessions:
        session_keywords = Counter()
        session_time = datetime.fromtimestamp(
            min(ts_array[i] for i in session_indices)
        ).strftime('%Y-%m-%d %H:%M')
        for i in session_indices:
            session_keywords.update(file_tokens[i])
        top_kws = [kw for kw, _ in session_keywords.most_common(3)]
        named_sessions.append({
            'indices': session_indices,
            'files': [files[i]['filename'] for i in session_indices],
            'keywords': top_kws,
            'time': session_time,
            'size': len(session_indices),
            'name': f"{session_time} — {', '.join(top_kws)}",
        })
    
    # ─── 6. Combine weighted matrix ───────────────────────────
    # Scale each feature block by its weight
    combined = np.hstack([
        tfidf * weights['filename_tokens'],
        tfidf * weights['content_keywords'],  # Same tokens, double-weighted
        ext_matrix * weights['extension'],
        temporal_matrix * weights['temporal'],
    ])
    
    # ─── 7. Keyword co-occurrence graph ───────────────────────
    keyword_graph = defaultdict(lambda: defaultdict(int))
    for tokens in file_tokens:
        unique = list(set(tokens))
        for i in range(len(unique)):
            for j in range(i + 1, len(unique)):
                keyword_graph[unique[i]][unique[j]] += 1
                keyword_graph[unique[j]][unique[i]] += 1
    
    return {
        'matrix': combined,
        'file_index': [f['filename'] for f in files],
        'file_paths': [f['filepath'] for f in files],
        'vocab': vocab,
        'extensions': all_exts,
        'temporal_sessions': named_sessions,
        'keyword_graph': dict(keyword_graph),
        'timestamps': timestamps,
        'n_files': n_files,
    }


def cluster_files(feature_data: dict, algorithm: str = 'kmeans',
                  n_clusters: int = None, min_cluster_size: int = 3) -> dict:
    """Run clustering on the feature matrix.
    
    Returns clusters with auto-generated names from top keywords.
    """
    matrix = feature_data['matrix']
    n_files = feature_data['n_files']
    
    if n_files < 3:
        return {'clusters': [], 'error': 'Too few files to cluster'}
    
    # Auto-determine cluster count if not specified
    if n_clusters is None:
        # Rough heuristic: sqrt(n) capped at 15
        n_clusters = min(max(int(np.sqrt(n_files)), 2), 15)
    
    if algorithm == 'kmeans':
        from sklearn.cluster import KMeans
        model = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        labels = model.fit_predict(matrix)
    
    elif algorithm == 'dbscan':
        from sklearn.cluster import DBSCAN
        # Estimate eps from pairwise distances
        from sklearn.metrics import pairwise_distances
        dists = pairwise_distances(matrix)
        # Use the median of k-nearest-neighbor distances
        k = min(5, n_files - 1)
        knn_dists = np.sort(dists, axis=1)[:, k]
        eps = np.median(knn_dists) * 1.2
        model = DBSCAN(eps=eps, min_samples=min_cluster_size)
        labels = model.fit_predict(matrix)
    
    elif algorithm == 'hdbscan':
        try:
            import hdbscan
            model = hdbscan.HDBSCAN(min_cluster_size=min_cluster_size)
            labels = model.fit_predict(matrix)
        except ImportError:
            # Fallback to kmeans
            from sklearn.cluster import KMeans
            model = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            labels = model.fit_predict(matrix)
    
    else:
        raise ValueError(f"Unknown algorithm: {algorithm}")
    
    # ─── Build cluster summaries ──────────────────────────────
    clusters = defaultdict(list)
    for i, label in enumerate(labels):
        clusters[label].append(i)
    
    result = []
    vocab = feature_data['vocab']
    
    for label, indices in sorted(clusters.items()):
        if label == -1:
            cluster_name = "UNCLUSTERED"
        else:
            # Name from top TF-IDF terms in this cluster
            cluster_tfidf = feature_data['matrix'][indices].mean(axis=0)
            # Get top terms from the vocabulary portion
            vocab_scores = cluster_tfidf[:len(vocab)]
            top_indices = np.argsort(vocab_scores)[-3:][::-1]
            top_terms = [vocab[i] for i in top_indices if vocab_scores[i] > 0]
            cluster_name = ' + '.join(top_terms) if top_terms else f"Cluster {label}"
        
        # Extension distribution
        ext_counts = Counter()
        for i in indices:
            ext = Path(feature_data['file_paths'][i]).suffix.lower()
            ext_counts[ext] += 1
        
        # Time range
        times = [feature_data['timestamps'][i] for i in indices]
        time_range = None
        if any(t > 0 for t in times):
            valid = [t for t in times if t > 0]
            time_range = {
                'earliest': datetime.fromtimestamp(min(valid)).isoformat(),
                'latest': datetime.fromtimestamp(max(valid)).isoformat(),
            }
        
        result.append({
            'id': int(label),
            'name': cluster_name,
            'size': len(indices),
            'files': [feature_data['file_index'][i] for i in indices],
            'file_paths': [feature_data['file_paths'][i] for i in indices],
            'extensions': dict(ext_counts),
            'time_range': time_range,
        })
    
    return {
        'clusters': sorted(result, key=lambda x: -x['size']),
        'n_clusters': len([c for c in result if c['id'] != -1]),
        'n_unclustered': len(clusters.get(-1, [])),
        'algorithm': algorithm,
        'temporal_sessions': feature_data['temporal_sessions'],
    }


def print_clusters(result: dict):
    """Pretty-print clustering results."""
    print(f"\n{'='*60}")
    print(f"  UNSUPERVISED CLUSTERING — {result['n_clusters']} clusters found")
    print(f"  Algorithm: {result['algorithm']}")
    if result['n_unclustered']:
        print(f"  Unclustered: {result['n_unclustered']} files")
    print(f"{'='*60}")
    
    for c in result['clusters']:
        label = '  NOISE' if c['id'] == -1 else f"  [{c['name'].upper()}]"
        print(f"\n{label} — {c['size']} files")
        exts = ', '.join(f"{e}({n})" for e, n in sorted(c['extensions'].items(), key=lambda x: -x[1])[:5])
        print(f"    Extensions: {exts}")
        if c['time_range']:
            print(f"    Time range: {c['time_range']['earliest'][:10]} → {c['time_range']['latest'][:10]}")
        for f in c['files'][:8]:
            print(f"      {f}")
        if len(c['files']) > 8:
            print(f"      ... +{len(c['files']) - 8} more")
    
    if result.get('temporal_sessions'):
        print(f"\n  TEMPORAL SESSIONS ({len(result['temporal_sessions'])} detected):")
        for s in result['temporal_sessions'][:5]:
            print(f"    {s['name']} ({s['size']} files)")
    
    print(f"{'='*60}\n")
