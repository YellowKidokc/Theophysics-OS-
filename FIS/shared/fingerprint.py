"""
Content Fingerprinter & Similarity Finder
==========================================
POF 2828 | 2026-06-15

Extracts text from any document type, generates content fingerprints,
finds near-duplicates across folders regardless of file format.

Supports: .html, .md, .txt, .docx, .pdf (text-based)

Usage:
  python fingerprint.py FOLDER1 FOLDER2 ...
  python fingerprint.py FOLDER1 FOLDER2 --threshold 0.7
  python fingerprint.py FOLDER1 --report fingerprint_report.json
"""
from __future__ import annotations
import hashlib, json, re, sys, os
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import Optional
import argparse

# ── Text extraction by file type ──

def _strip_html_to_text(html: str) -> str:
    """Strip HTML tags, scripts, styles — keep only text content."""
    # Remove script/style blocks
    text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL|re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL|re.IGNORECASE)
    text = re.sub(r'<nav[^>]*>.*?</nav>', '', text, flags=re.DOTALL|re.IGNORECASE)
    text = re.sub(r'<footer[^>]*>.*?</footer>', '', text, flags=re.DOTALL|re.IGNORECASE)
    text = re.sub(r'<header[^>]*>.*?</header>', '', text, flags=re.DOTALL|re.IGNORECASE)
    # Remove tags
    text = re.sub(r'<[^>]+>', ' ', text)
    # Decode entities
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'&#?\w+;', ' ', text)
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _html_main_with_bs4(html: str) -> str:
    """Extract semantic/main article body with BeautifulSoup when available."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return ""

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
        tag.decompose()

    selectors = [
        "article",
        "main",
        "[role='main']",
        ".content",
        ".post",
        ".entry",
        ".article",
        ".page-content",
        ".main-content",
        "#content",
        "#main",
        "#article",
    ]
    candidates = []
    for selector in selectors:
        for node in soup.select(selector):
            text = node.get_text(" ", strip=True)
            words = len(text.split())
            if words >= 50:
                candidates.append((words, text))
    if candidates:
        candidates.sort(reverse=True, key=lambda x: x[0])
        return candidates[0][1]
    return ""


def _html_largest_block(html: str) -> str:
    """Fallback: choose the largest likely content block, not the full shell."""
    cleaned = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL|re.IGNORECASE)
    cleaned = re.sub(r'<style[^>]*>.*?</style>', '', cleaned, flags=re.DOTALL|re.IGNORECASE)
    cleaned = re.sub(r'<nav[^>]*>.*?</nav>', '', cleaned, flags=re.DOTALL|re.IGNORECASE)
    cleaned = re.sub(r'<footer[^>]*>.*?</footer>', '', cleaned, flags=re.DOTALL|re.IGNORECASE)
    cleaned = re.sub(r'<header[^>]*>.*?</header>', '', cleaned, flags=re.DOTALL|re.IGNORECASE)
    cleaned = re.sub(r'<aside[^>]*>.*?</aside>', '', cleaned, flags=re.DOTALL|re.IGNORECASE)

    blocks = re.findall(
        r'<(article|main|section|div)[^>]*>(.*?)</\1>',
        cleaned,
        flags=re.DOTALL | re.IGNORECASE,
    )
    scored = []
    for _, block in blocks:
        text = _strip_html_to_text(block)
        words = len(text.split())
        if words >= 50:
            scored.append((words, text))
    if not scored:
        return ""
    scored.sort(reverse=True, key=lambda x: x[0])
    best_words, best_text = scored[0]
    if len(scored) > 1 and scored[1][0] >= best_words * 0.65:
        return f"{best_text} {scored[1][1]}"
    return best_text


def extract_text_html(path: Path) -> str:
    """Extract article/main HTML text before fingerprinting."""
    html = path.read_text(encoding="utf-8-sig", errors="replace")
    body = _html_main_with_bs4(html)
    if not body:
        body = _html_largest_block(html)
    if body:
        return re.sub(r'\s+', ' ', body).strip()
    return _strip_html_to_text(html)


def extract_text_md(path: Path) -> str:
    """Read markdown as-is (it's already mostly text)."""
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    # Strip YAML frontmatter
    text = re.sub(r'^---\s*\n.*?\n---\s*\n', '', text, flags=re.DOTALL)
    # Remove markdown syntax but keep words
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)  # images
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)  # links
    text = re.sub(r'[#*_`~>|]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def extract_text_docx(path: Path) -> str:
    """Extract text from Word documents."""
    try:
        from docx import Document
        doc = Document(str(path))
        return ' '.join(p.text for p in doc.paragraphs if p.text.strip())
    except ImportError:
        # Fallback: read raw XML
        import zipfile
        with zipfile.ZipFile(str(path)) as z:
            xml = z.read('word/document.xml').decode('utf-8', errors='replace')
            text = re.sub(r'<[^>]+>', ' ', xml)
            return re.sub(r'\s+', ' ', text).strip()
    except Exception:
        return ""


def extract_text_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


EXTRACTORS = {
    '.html': extract_text_html,
    '.htm': extract_text_html,
    '.md': extract_text_md,
    '.markdown': extract_text_md,
    '.txt': extract_text_txt,
    '.docx': extract_text_docx,
}

SUPPORTED = set(EXTRACTORS.keys())

# ── Fingerprinting engine ──

def normalize(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def shingle(text: str, k: int = 5) -> set[str]:
    """Generate k-word shingles from text."""
    words = text.split()
    if len(words) < k:
        return {' '.join(words)} if words else set()
    return {' '.join(words[i:i+k]) for i in range(len(words) - k + 1)}


def minhash_signature(shingles: set[str], num_hashes: int = 128) -> list[int]:
    """Generate MinHash signature for a set of shingles."""
    max_hash = 2**128 - 1
    if not shingles:
        return [max_hash] * num_hashes
    sig = [max_hash] * num_hashes
    for s in shingles:
        for i in range(num_hashes):
            h = int(hashlib.md5(f"{i}:{s}".encode()).hexdigest(), 16)
            if h < sig[i]:
                sig[i] = h
    return sig


def jaccard_minhash(sig1: list[int], sig2: list[int]) -> float:
    """Estimate Jaccard similarity from MinHash signatures."""
    if not sig1 or not sig2:
        return 0.0
    matches = sum(1 for a, b in zip(sig1, sig2) if a == b)
    return matches / len(sig1)


def content_hash(text: str) -> str:
    """SHA256 of normalized text for exact-duplicate detection."""
    return hashlib.sha256(normalize(text).encode()).hexdigest()[:16]

# ── Document processing ──

def process_file(path: Path) -> Optional[dict]:
    """Extract text, generate fingerprint for one file."""
    ext = path.suffix.lower()
    if ext not in SUPPORTED:
        return None
    extractor = EXTRACTORS[ext]
    try:
        text = extractor(path)
    except Exception as e:
        return {"path": str(path), "error": str(e)}
    if len(text.strip()) < 50:
        return None  # skip near-empty files
    norm = normalize(text)
    word_count = len(norm.split())
    shingles_set = shingle(norm, k=5)
    return {
        "path": str(path),
        "ext": ext,
        "word_count": word_count,
        "content_hash": content_hash(text),
        "signature": minhash_signature(shingles_set, num_hashes=128),
        "title": text[:100].strip(),
    }

# ── Main ──

def find_duplicates(docs: list[dict], threshold: float = 0.7) -> tuple[list, list]:
    """Find exact duplicates and near-duplicates."""
    # Exact duplicates (same content hash)
    hash_groups = defaultdict(list)
    for d in docs:
        if "error" not in d:
            hash_groups[d["content_hash"]].append(d["path"])
    exact_dupes = {h: paths for h, paths in hash_groups.items() if len(paths) > 1}

    # Near-duplicates (MinHash similarity above threshold)
    near_dupes = []
    n = len(docs)
    valid = [d for d in docs if "error" not in d]
    for i in range(len(valid)):
        for j in range(i + 1, len(valid)):
            # Skip if already exact duplicate
            if valid[i]["content_hash"] == valid[j]["content_hash"]:
                continue
            sim = jaccard_minhash(valid[i]["signature"], valid[j]["signature"])
            if sim >= threshold:
                near_dupes.append({
                    "file_a": valid[i]["path"],
                    "file_b": valid[j]["path"],
                    "similarity": round(sim, 3),
                    "words_a": valid[i]["word_count"],
                    "words_b": valid[j]["word_count"],
                })
    near_dupes.sort(key=lambda x: x["similarity"], reverse=True)
    return exact_dupes, near_dupes

def main():
    parser = argparse.ArgumentParser(description="Content fingerprinter & duplicate finder")
    parser.add_argument("folders", nargs="+", help="Folders to scan")
    parser.add_argument("--threshold", type=float, default=0.7, help="Similarity threshold (0-1, default 0.7)")
    parser.add_argument("--report", type=str, default=None, help="Save JSON report to this path")
    parser.add_argument("--max-files", type=int, default=500, help="Max files to compare (default 500)")
    args = parser.parse_args()

    print("=" * 70)
    print("CONTENT FINGERPRINTER")
    print(f"Threshold: {args.threshold}")
    print(f"Scanning: {', '.join(args.folders)}")
    print("=" * 70)

    # Collect files
    all_files = []
    for folder in args.folders:
        p = Path(folder)
        if not p.exists():
            print(f"  WARNING: {folder} not found, skipping")
            continue
        for ext in SUPPORTED:
            all_files.extend(p.rglob(f"*{ext}"))

    print(f"\nFound {len(all_files)} supported files")
    if len(all_files) > args.max_files:
        print(f"  Limiting to {args.max_files} (use --max-files to increase)")
        all_files = all_files[:args.max_files]

    # Process
    docs = []
    errors = 0
    for i, f in enumerate(all_files):
        if (i + 1) % 50 == 0:
            print(f"  Processed {i+1}/{len(all_files)}...")
        result = process_file(f)
        if result:
            if "error" in result:
                errors += 1
            else:
                docs.append(result)

    print(f"\nFingerprinted {len(docs)} documents ({errors} errors)")
    print(f"\nFinding duplicates (threshold={args.threshold})...")

    exact_dupes, near_dupes = find_duplicates(docs, args.threshold)

    # Report
    print(f"\n{'='*70}")
    print(f"EXACT DUPLICATES: {len(exact_dupes)} groups")
    for h, paths in list(exact_dupes.items())[:15]:
        print(f"\n  [{h}] ({len(paths)} copies)")
        for p in paths:
            print(f"    {p}")

    print(f"\n{'='*70}")
    print(f"NEAR-DUPLICATES: {len(near_dupes)} pairs (>{args.threshold:.0%} similar)")
    for pair in near_dupes[:20]:
        print(f"\n  {pair['similarity']:.0%} similar:")
        print(f"    A: {pair['file_a']} ({pair['words_a']} words)")
        print(f"    B: {pair['file_b']} ({pair['words_b']} words)")

    # Save report
    report = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "folders": args.folders,
        "threshold": args.threshold,
        "total_files": len(all_files),
        "fingerprinted": len(docs),
        "exact_duplicate_groups": len(exact_dupes),
        "near_duplicate_pairs": len(near_dupes),
        "exact_duplicates": {h: paths for h, paths in exact_dupes.items()},
        "near_duplicates": near_dupes,
    }

    report_path = args.report or str(Path(args.folders[0]) / f"fingerprint_report_{datetime.now():%Y%m%d_%H%M%S}.json")
    try:
        Path(report_path).write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        print(f"\nFull report: {report_path}")
    except Exception as e:
        print(f"\nCould not save report: {e}")

    print("=" * 70)


if __name__ == "__main__":
    main()
