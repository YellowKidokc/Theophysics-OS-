"""Manual File Sorter — hands-on sorting, dedup, flatten, extension grouping.
Usage:
    python manual_sort.py scan <path>              — show stats (extensions, sizes, dupes)
    python manual_sort.py sort-ext <path> <output>  — group files by extension into folders
    python manual_sort.py flatten <path>            — collapse all subfolders to one level
    python manual_sort.py dupes <path>              — find duplicates (name + MD5)
    python manual_sort.py dedup <path> --keep biggest|smallest|newest|oldest|first
"""

import hashlib
import os
import shutil
import sys
from collections import defaultdict
from pathlib import Path
from datetime import datetime


# ─── SCAN ────────────────────────────────────────────────────────────────────

def scan_directory(root: str) -> dict:
    """Scan directory and return stats."""
    root = Path(root)
    ext_counts = defaultdict(int)
    ext_sizes = defaultdict(int)
    kind_map = {
        'image': {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.svg', '.ico', '.tiff', '.tif'},
        'document': {'.pdf', '.docx', '.doc', '.pptx', '.ppt', '.xlsx', '.xls', '.odt'},
        'text': {'.txt', '.md', '.csv', '.json', '.yaml', '.yml', '.xml', '.ini', '.cfg', '.log', '.toml'},
        'code': {'.py', '.js', '.ts', '.jsx', '.tsx', '.html', '.css', '.rs', '.go', '.java', '.c', '.cpp', '.h'},
        'archive': {'.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz'},
        'audio': {'.mp3', '.wav', '.flac', '.ogg', '.m4a', '.aac', '.wma'},
        'video': {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm'},
        'subtitle': {'.srt', '.vtt', '.sub', '.ass', '.ssa'},
        'executable': {'.exe', '.msi', '.bat', '.cmd', '.sh', '.ps1'},
        'font': {'.ttf', '.otf', '.woff', '.woff2'},
    }

    kind_counts = defaultdict(int)
    total_files = 0
    total_size = 0
    folder_count = 0
    all_files = []

    for dirpath, dirnames, filenames in os.walk(root):
        folder_count += len(dirnames)
        for fname in filenames:
            fpath = Path(dirpath) / fname
            try:
                size = fpath.stat().st_size
                mtime = fpath.stat().st_mtime
            except OSError:
                continue
            ext = fpath.suffix.lower()
            ext_counts[ext] += 1
            ext_sizes[ext] += size
            total_files += 1
            total_size += size
            all_files.append({
                'path': str(fpath),
                'name': fname,
                'stem': fpath.stem,
                'ext': ext,
                'size': size,
                'mtime': mtime,
            })
            # Classify by kind
            classified = False
            for kind, exts in kind_map.items():
                if ext in exts:
                    kind_counts[kind] += 1
                    classified = True
                    break
            if not classified:
                kind_counts['other'] += 1

    return {
        'root': str(root),
        'total_files': total_files,
        'total_size': total_size,
        'folder_count': folder_count,
        'ext_counts': dict(sorted(ext_counts.items(), key=lambda x: -x[1])),
        'ext_sizes': dict(sorted(ext_sizes.items(), key=lambda x: -x[1])),
        'kind_counts': dict(sorted(kind_counts.items(), key=lambda x: -x[1])),
        'all_files': all_files,
    }


def print_scan(stats: dict):
    """Pretty-print scan results."""
    print(f"\n{'='*60}")
    print(f"  SCAN: {stats['root']}")
    print(f"{'='*60}")
    print(f"  Total files:   {stats['total_files']:,}")
    print(f"  Total size:    {format_size(stats['total_size'])}")
    print(f"  Folders:       {stats['folder_count']:,}")
    print(f"\n  BY KIND:")
    for kind, count in stats['kind_counts'].items():
        print(f"    {kind:15s} {count:>6,}")
    print(f"\n  TOP EXTENSIONS:")
    for ext, count in list(stats['ext_counts'].items())[:20]:
        ext_display = ext if ext else '(no ext)'
        size = format_size(stats['ext_sizes'].get(ext, 0))
        print(f"    {ext_display:15s} {count:>6,}  ({size})")
    print(f"{'='*60}\n")


def format_size(n: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


# ─── SORT BY EXTENSION ───────────────────────────────────────────────────────

def sort_by_extension(root: str, output: str, dry_run: bool = False):
    """Group files by extension into folders."""
    stats = scan_directory(root)
    output = Path(output)
    ops = []

    for f in stats['all_files']:
        ext = f['ext'].lstrip('.') or 'no_extension'
        dest_dir = output / ext.upper()
        dest_file = dest_dir / f['name']
        # Handle name collisions
        if dest_file.exists() or any(o['dest'] == str(dest_file) for o in ops):
            stem = Path(f['name']).stem
            suffix = Path(f['name']).suffix
            counter = 1
            while True:
                new_name = f"{stem}_{counter}{suffix}"
                dest_file = dest_dir / new_name
                if not dest_file.exists() and not any(o['dest'] == str(dest_file) for o in ops):
                    break
                counter += 1
        ops.append({'src': f['path'], 'dest': str(dest_file), 'dir': str(dest_dir)})

    # Summary
    dirs_needed = set(o['dir'] for o in ops)
    print(f"\n  Sort by extension: {len(ops)} files → {len(dirs_needed)} folders")
    for d in sorted(dirs_needed):
        count = sum(1 for o in ops if o['dir'] == d)
        print(f"    {Path(d).name:15s} → {count:>5} files")

    if dry_run:
        print("\n  [DRY RUN — no files moved]")
        return ops

    confirm = input("\n  Proceed? (y/n): ").strip().lower()
    if confirm != 'y':
        print("  Cancelled.")
        return []

    for o in ops:
        Path(o['dir']).mkdir(parents=True, exist_ok=True)
        shutil.copy2(o['src'], o['dest'])
    print(f"  Done. {len(ops)} files sorted.")
    return ops


# ─── FLATTEN ─────────────────────────────────────────────────────────────────

def flatten_directory(root: str, dry_run: bool = False):
    """Move all files from subfolders to root level, remove empty folders."""
    root = Path(root)
    ops = []
    for dirpath, dirnames, filenames in os.walk(root):
        if Path(dirpath) == root:
            continue  # Skip root itself
        for fname in filenames:
            src = Path(dirpath) / fname
            dest = root / fname
            # Handle collisions
            if dest.exists() or any(o['dest'] == str(dest) for o in ops):
                stem = Path(fname).stem
                suffix = Path(fname).suffix
                counter = 1
                while True:
                    new_name = f"{stem}_{counter}{suffix}"
                    dest = root / new_name
                    if not dest.exists() and not any(o['dest'] == str(dest) for o in ops):
                        break
                    counter += 1
            ops.append({'src': str(src), 'dest': str(dest)})

    print(f"\n  Flatten: {len(ops)} files to move to root")

    if dry_run:
        print("  [DRY RUN — no files moved]")
        return ops

    confirm = input("  Proceed? (y/n): ").strip().lower()
    if confirm != 'y':
        print("  Cancelled.")
        return []

    for o in ops:
        shutil.move(o['src'], o['dest'])

    # Remove empty directories (bottom-up)
    for dirpath, dirnames, filenames in os.walk(root, topdown=False):
        if Path(dirpath) != root and not os.listdir(dirpath):
            os.rmdir(dirpath)
            print(f"    Removed empty: {dirpath}")

    print(f"  Done. {len(ops)} files flattened.")
    return ops


# ─── DUPLICATE FINDER ────────────────────────────────────────────────────────

def md5_hash(filepath: str, chunk_size: int = 8192) -> str:
    """Compute MD5 hash of a file."""
    h = hashlib.md5()
    with open(filepath, 'rb') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def find_duplicates(root: str, by: str = 'both') -> list:
    """Find duplicate files. by='name', 'hash', or 'both'."""
    stats = scan_directory(root)
    files = stats['all_files']

    # Group by name
    name_groups = defaultdict(list)
    for f in files:
        name_groups[f['name'].lower()].append(f)

    # Group by hash (only for files with same name, or all if by='hash')
    dupe_groups = []

    if by == 'name':
        for name, group in name_groups.items():
            if len(group) > 1:
                dupe_groups.append({
                    'match_key': name,
                    'match_type': 'name',
                    'files': group,
                    'count': len(group),
                })
    elif by == 'hash':
        hash_groups = defaultdict(list)
        print("  Computing hashes...")
        for i, f in enumerate(files):
            if i % 100 == 0 and i > 0:
                print(f"    ...{i}/{len(files)}")
            try:
                h = md5_hash(f['path'])
                f['md5'] = h
                hash_groups[h].append(f)
            except OSError:
                continue
        for h, group in hash_groups.items():
            if len(group) > 1:
                dupe_groups.append({
                    'match_key': h,
                    'match_type': 'hash',
                    'files': group,
                    'count': len(group),
                })
    else:  # both
        # First pass: name matches
        name_dupes = {name: group for name, group in name_groups.items() if len(group) > 1}
        # Second pass: hash within name groups + hash across all
        hash_groups = defaultdict(list)
        print("  Computing hashes for name-matched files...")
        checked = set()
        for name, group in name_dupes.items():
            for f in group:
                try:
                    h = md5_hash(f['path'])
                    f['md5'] = h
                    hash_groups[h].append(f)
                    checked.add(f['path'])
                except OSError:
                    continue

        # Also check size-matched files not caught by name
        size_groups = defaultdict(list)
        for f in files:
            if f['path'] not in checked and f['size'] > 0:
                size_groups[f['size']].append(f)
        print("  Checking size-matched files for hash dupes...")
        for size, group in size_groups.items():
            if len(group) > 1:
                for f in group:
                    try:
                        h = md5_hash(f['path'])
                        f['md5'] = h
                        hash_groups[h].append(f)
                    except OSError:
                        continue

        for h, group in hash_groups.items():
            if len(group) > 1:
                dupe_groups.append({
                    'match_key': h,
                    'match_type': 'hash',
                    'files': group,
                    'count': len(group),
                })

    return sorted(dupe_groups, key=lambda x: -x['count'])


def print_dupes(dupe_groups: list):
    """Display duplicate groups."""
    if not dupe_groups:
        print("\n  No duplicates found.")
        return
    total_dupes = sum(g['count'] - 1 for g in dupe_groups)
    total_waste = sum(sum(f['size'] for f in g['files'][1:]) for g in dupe_groups)
    print(f"\n{'='*60}")
    print(f"  DUPLICATES: {len(dupe_groups)} groups, {total_dupes} extra copies")
    print(f"  Wasted space: {format_size(total_waste)}")
    print(f"{'='*60}")
    for i, g in enumerate(dupe_groups[:50]):  # Show first 50 groups
        print(f"\n  Group {i+1} [{g['match_type']}] — {g['count']} copies:")
        for j, f in enumerate(g['files']):
            marker = '  ★' if j == 0 else '   '
            age = datetime.fromtimestamp(f['mtime']).strftime('%Y-%m-%d')
            print(f"  {marker} {format_size(f['size']):>10s}  {age}  {f['path']}")
    if len(dupe_groups) > 50:
        print(f"\n  ...and {len(dupe_groups) - 50} more groups")


def dedup(root: str, keep: str = 'biggest', dry_run: bool = False, by: str = 'both'):
    """Remove duplicates, keeping one per group based on strategy.

    keep: 'biggest', 'smallest', 'newest', 'oldest', 'first'
    """
    dupe_groups = find_duplicates(root, by=by)
    if not dupe_groups:
        print("\n  No duplicates found.")
        return []

    print_dupes(dupe_groups)

    # Pick winners
    to_delete = []
    for g in dupe_groups:
        files = g['files']
        if keep == 'biggest':
            files_sorted = sorted(files, key=lambda f: -f['size'])
        elif keep == 'smallest':
            files_sorted = sorted(files, key=lambda f: f['size'])
        elif keep == 'newest':
            files_sorted = sorted(files, key=lambda f: -f['mtime'])
        elif keep == 'oldest':
            files_sorted = sorted(files, key=lambda f: f['mtime'])
        else:  # first
            files_sorted = files

        winner = files_sorted[0]
        losers = files_sorted[1:]
        for loser in losers:
            to_delete.append({
                'path': loser['path'],
                'reason': f"dupe of {winner['path']}",
                'size': loser['size'],
            })

    total_recover = sum(d['size'] for d in to_delete)
    print(f"\n  Strategy: keep {keep}")
    print(f"  Files to delete: {len(to_delete)}")
    print(f"  Space recovered: {format_size(total_recover)}")

    if dry_run:
        print("  [DRY RUN — no files deleted]")
        return to_delete

    confirm = input(f"\n  Delete {len(to_delete)} files? (y/n): ").strip().lower()
    if confirm != 'y':
        print("  Cancelled.")
        return []

    deleted = 0
    for d in to_delete:
        try:
            os.remove(d['path'])
            deleted += 1
        except OSError as e:
            print(f"    Error deleting {d['path']}: {e}")

    print(f"  Done. {deleted} files deleted, {format_size(total_recover)} recovered.")
    return to_delete


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1].lower()
    path = sys.argv[2]

    if not os.path.exists(path):
        print(f"  Error: path does not exist: {path}")
        sys.exit(1)

    if cmd == 'scan':
        stats = scan_directory(path)
        print_scan(stats)

    elif cmd == 'sort-ext':
        output = sys.argv[3] if len(sys.argv) > 3 else os.path.join(path, '_sorted')
        dry = '--dry' in sys.argv
        sort_by_extension(path, output, dry_run=dry)

    elif cmd == 'flatten':
        dry = '--dry' in sys.argv
        flatten_directory(path, dry_run=dry)

    elif cmd == 'dupes':
        by = 'both'
        if '--by' in sys.argv:
            idx = sys.argv.index('--by')
            by = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else 'both'
        dupe_groups = find_duplicates(path, by=by)
        print_dupes(dupe_groups)

    elif cmd == 'dedup':
        keep = 'biggest'
        if '--keep' in sys.argv:
            idx = sys.argv.index('--keep')
            keep = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else 'biggest'
        by = 'both'
        if '--by' in sys.argv:
            idx = sys.argv.index('--by')
            by = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else 'both'
        dry = '--dry' in sys.argv
        dedup(path, keep=keep, dry_run=dry, by=by)

    else:
        print(f"  Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == '__main__':
    main()
