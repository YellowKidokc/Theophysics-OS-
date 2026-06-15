"""API Server — bridges the GUI to the classification + preference engine.

Runs on port 8450. The React GUI talks to this via HTTP.

Endpoints:
  GET  /api/scan?path=...&top=true    — classify files, return JSON
  POST /api/decide                     — record approve/reject/override
  GET  /api/stats                      — preference engine stats
  POST /api/nlp-classify               — run NLP tier on specific files
  GET  /api/predict?keywords=...&ext=. — get Markov prediction
"""

import json
import os
import sys
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path
from collections import Counter

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from auto_sort import classify_file, classify_directory, DOMAIN_RULES
from preference_engine import record_decision, predict_domain, get_engine_stats, get_auto_approve_threshold
from naming_engine import NamingEngine, clean_filename, PRESETS
from hub_engines import (
    baseline_rename_plan,
    fis_text_classify,
    hub_status,
    manual_scan,
    organizer_preview,
    rename_preview,
)
from sorter_cache import (
    cache_classification,
    cache_decision,
    cache_nlp_result,
    cache_status,
    cached_file_paths,
    cached_folder_children,
    cached_folder_summary,
    cached_rename_plan,
    cached_rename_sample,
    cached_theme_clusters,
    decide_organization_finding,
    finish_scan,
    folderbrain_summary,
    grouped_organization_findings,
    init_db,
    list_roots,
    recent_cached_files,
    recent_organization_findings,
    recent_actions,
    record_action,
    register_root,
    scan_inventory,
    seed_demo_roots,
    start_scan,
    update_action_status,
    write_folderbrain,
    write_folderbrains,
)


TEMPLATES = {
    "station": {
        "folders": ["INPUT", "OUTPUT", "_LOGS"],
        "files": {
            "station.json": '{\n  "station_id": "",\n  "name": "",\n  "status": "draft",\n  "inputs": [],\n  "outputs": []\n}',
            "README.md": "# Station\n\nDescribe this station.\n",
            "RUN.bat": '@echo off\necho Starting station...\npython -m station %*\n',
            "requirements.txt": "# Dependencies\n",
        }
    },
    "job": {
        "folders": [],
        "files": {
            "job.json": '{\n  "job_id": "",\n  "name": "",\n  "workflow": [],\n  "status": "draft"\n}',
        }
    },
    "project": {
        "folders": ["docs", "src", "assets", "_archive"],
        "files": {
            "README.md": "# Project\n\nDescribe this project.\n",
            ".gitignore": "__pycache__/\n*.pyc\n.env\nnode_modules/\n",
        }
    },
    "brain": {
        "folders": ["_front_door", "_inbox", "_outbox", "_logs", "_state", "_processed"],
        "files": {
            "HEALTHCHECK.bat": "@echo off\necho Checking health...\ndir /b _inbox\npause\n",
            "README.md": "# Brain Subsystem\n\nDescribe this subsystem.\n",
            "START.bat": "@echo off\necho Starting subsystem...\npause\n",
            "PROCESS_INBOX.bat": "@echo off\necho Processing inbox...\ndir /b _inbox\npause\n",
        }
    },
    "empty": {"folders": [], "files": {}},
}


def _split_exclusions(raw):
    defaults = {
        ".git", ".svn", ".hg", ".venv", "venv", "env", "node_modules",
        "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
        ".obsidian\\plugins", "_gsdata_", "$recycle.bin",
    }
    custom = {x.strip().lower() for x in (raw or "").split(",") if x.strip()}
    return defaults | custom


def _folder_kind(folder, counts, total_files, target_ext, prod_hints):
    html_count = counts.get(".html", 0) + counts.get(".htm", 0)
    md_count = counts.get(".md", 0) + counts.get(".markdown", 0) + counts.get(".canvas", 0)
    js_count = counts.get(".js", 0) + counts.get(".jsx", 0) + counts.get(".ts", 0) + counts.get(".tsx", 0)
    css_count = counts.get(".css", 0) + counts.get(".scss", 0) + counts.get(".sass", 0)
    web_count = html_count + js_count + css_count
    html_pct = round((html_count / total_files) * 100, 1) if total_files else 0
    md_pct = round((md_count / total_files) * 100, 1) if total_files else 0
    web_pct = round((web_count / total_files) * 100, 1) if total_files else 0
    target_pct = round((counts.get(target_ext, 0) / total_files) * 100, 1) if total_files else 0
    has_obsidian = os.path.isdir(os.path.join(folder, ".obsidian"))

    if prod_hints >= 3:
        return "production_web_project", "Keep separate; treat as an app/project, not loose webpages."
    if has_obsidian or (md_count >= 5 and md_pct >= 35 and prod_hints == 0):
        if html_count:
            return "obsidian_or_web_capture_mix", "Review before moving; notes and captured pages are mixed."
        return "obsidian_vault_or_notes", "Protect as notes/knowledge folder."
    if target_ext in (".html", ".htm") and target_pct >= 60:
        return "html_archive_or_webpages", "Candidate for web-page/archive grouping."
    if html_pct >= 40 or web_pct >= 65:
        return "webpage_heavy_mixed", "Likely web material; inspect before combining."
    if counts.get(target_ext, 0):
        return "some_target_extension_present", "Contains the extension, but it is not dominant."
    return "not_target_focused", "No strong match for this extension."


def folder_composition_scan(root, extension="html", threshold=60, max_folders=400, max_files_per_folder=20000, exclude=""):
    """Read-only folder composition scan for Advanced Mode."""
    if not root or not os.path.exists(root):
        return {"error": f"Path not found: {root}"}
    ext = (extension or "html").strip().lower()
    if not ext.startswith("."):
        ext = "." + ext
    threshold = max(0, min(100, int(float(threshold or 60))))
    max_folders = max(1, min(2000, int(max_folders or 400)))
    max_files_per_folder = max(100, min(200000, int(max_files_per_folder or 20000)))
    exclusions = _split_exclusions(exclude)

    prod_files = {
        "package.json", "vite.config.js", "vite.config.ts", "next.config.js",
        "tsconfig.json", "tailwind.config.js", "webpack.config.js",
        "astro.config.mjs", "svelte.config.js", "src-tauri",
    }
    prod_dirs = {"src", "app", "pages", "components", "public", "assets", "styles"}
    rows = []
    skipped = 0

    try:
        candidates = []
        for name in os.listdir(root):
            path = os.path.join(root, name)
            if os.path.isdir(path) and name.lower() not in exclusions:
                candidates.append(path)
        candidates = candidates[:max_folders]
    except Exception as exc:
        return {"error": str(exc)}

    for folder in candidates:
        counts = Counter()
        total_files = 0
        total_size = 0
        prod_hints = 0
        capped = False
        try:
            top_names = {x.lower() for x in os.listdir(folder)[:5000]}
            prod_hints += len(top_names & prod_files)
            prod_hints += len(top_names & prod_dirs)
        except Exception:
            top_names = set()

        for current, dirs, files in os.walk(folder):
            dirs[:] = [d for d in dirs if d.lower() not in exclusions]
            for filename in files:
                total_files += 1
                suffix = os.path.splitext(filename)[1].lower() or "(none)"
                counts[suffix] += 1
                try:
                    total_size += os.path.getsize(os.path.join(current, filename))
                except OSError:
                    pass
                if total_files >= max_files_per_folder:
                    capped = True
                    break
            if capped:
                break

        if total_files == 0:
            skipped += 1
            continue

        target_count = counts.get(ext, 0)
        if ext == ".html":
            target_count += counts.get(".htm", 0)
        target_pct = round((target_count / total_files) * 100, 1)
        kind, recommendation = _folder_kind(folder, counts, total_files, ext, prod_hints)
        top_ext = [{"ext": k, "count": v} for k, v in counts.most_common(6)]
        rows.append({
            "path": folder,
            "name": os.path.basename(folder),
            "file_count": total_files,
            "size_bytes": total_size,
            "target_ext": ext,
            "target_count": target_count,
            "target_pct": target_pct,
            "kind": kind,
            "recommendation": recommendation,
            "prod_hints": prod_hints,
            "top_ext": top_ext,
            "capped": capped,
            "matches_threshold": target_pct >= threshold,
        })

    rows.sort(key=lambda r: (not r["matches_threshold"], -r["target_pct"], -r["target_count"], r["name"].lower()))
    summary = Counter(r["kind"] for r in rows)
    return {
        "root": root,
        "target_ext": ext,
        "threshold": threshold,
        "folder_count": len(rows),
        "skipped_empty": skipped,
        "matching_count": sum(1 for r in rows if r["matches_threshold"]),
        "summary": dict(summary),
        "rows": rows,
        "matches": [r for r in rows if r["matches_threshold"]],
        "message": f"Found {sum(1 for r in rows if r['matches_threshold'])} folders at or above {threshold}% {ext}. Nothing was changed.",
    }


def folder_compare_scan(left, right, recursive=True, compare="relative_path", max_files=50000, exclude=""):
    """Read-only two-folder comparison for Advanced Mode."""
    if not left or not os.path.exists(left):
        return {"error": f"Left path not found: {left}"}
    if not right or not os.path.exists(right):
        return {"error": f"Right path not found: {right}"}
    if not os.path.isdir(left) or not os.path.isdir(right):
        return {"error": "Compare currently expects two folders."}

    exclusions = _split_exclusions(exclude)
    max_files = max(100, min(250000, int(max_files or 50000)))
    compare = (compare or "relative_path").strip().lower()

    def collect(root):
        items = {}
        skipped = 0
        capped = False
        for current, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d.lower() not in exclusions]
            for filename in files:
                if filename.lower() in exclusions:
                    skipped += 1
                    continue
                full = os.path.join(current, filename)
                rel = os.path.relpath(full, root).replace("\\", "/")
                if compare == "filename_only":
                    key = filename.lower()
                else:
                    key = rel.lower()
                try:
                    stat = os.stat(full)
                    size = stat.st_size
                    mtime = stat.st_mtime
                except OSError:
                    size = 0
                    mtime = 0
                bucket = items.setdefault(key, [])
                bucket.append({
                    "path": full,
                    "rel": rel,
                    "name": filename,
                    "size": size,
                    "mtime": mtime,
                    "mtime_iso": __import__("datetime").datetime.fromtimestamp(mtime).isoformat(timespec="seconds") if mtime else "",
                    "ext": os.path.splitext(filename)[1].lower() or "(none)",
                })
                if sum(len(v) for v in items.values()) >= max_files:
                    capped = True
                    break
            if capped or not recursive:
                break
        return items, skipped, capped

    left_items, left_skipped, left_capped = collect(left)
    right_items, right_skipped, right_capped = collect(right)
    keys = sorted(set(left_items) | set(right_items))
    only_left = []
    only_right = []
    changed = []
    same = []

    for key in keys:
        lvals = left_items.get(key, [])
        rvals = right_items.get(key, [])
        if lvals and not rvals:
            only_left.extend(lvals)
        elif rvals and not lvals:
            only_right.extend(rvals)
        else:
            l0 = lvals[0]
            r0 = rvals[0]
            row = {
                "key": key,
                "left": l0,
                "right": r0,
                "size_delta": r0["size"] - l0["size"],
                "newer_side": "right" if r0["mtime"] > l0["mtime"] else "left" if l0["mtime"] > r0["mtime"] else "same",
                "duplicate_count_left": len(lvals),
                "duplicate_count_right": len(rvals),
            }
            if l0["size"] == r0["size"]:
                same.append(row)
            else:
                changed.append(row)

    only_left.sort(key=lambda x: (x["rel"].lower(), x["size"]))
    only_right.sort(key=lambda x: (x["rel"].lower(), x["size"]))
    changed.sort(key=lambda x: (abs(x["size_delta"]), x["key"]), reverse=True)

    return {
        "left": left,
        "right": right,
        "recursive": recursive,
        "compare": compare,
        "left_count": sum(len(v) for v in left_items.values()),
        "right_count": sum(len(v) for v in right_items.values()),
        "same_count": len(same),
        "changed_count": len(changed),
        "only_left_count": len(only_left),
        "only_right_count": len(only_right),
        "skipped": left_skipped + right_skipped,
        "capped": left_capped or right_capped,
        "only_left": only_left[:300],
        "only_right": only_right[:300],
        "changed": changed[:300],
        "same_sample": same[:80],
        "suggested_actions": [
            {"label": "Copy right-only to left", "count": len(only_right), "action": "copy_right_to_left", "risk": "low"},
            {"label": "Copy left-only to right", "count": len(only_left), "action": "copy_left_to_right", "risk": "low"},
            {"label": "Review changed files", "count": len(changed), "action": "review_changed", "risk": "medium"},
            {"label": "Leave both sides alone", "count": len(keys), "action": "no_action", "risk": "none"},
        ],
        "message": f"Compared {sum(len(v) for v in left_items.values())} left files with {sum(len(v) for v in right_items.values())} right files. Nothing was changed.",
    }


def create_from_template(parent, name, template_id):
    """Create a folder structure from a template."""
    template = TEMPLATES.get(template_id, TEMPLATES["empty"])
    target = os.path.join(parent, name)
    if os.path.exists(target):
        return {"error": f"Folder already exists: {target}"}
    folders_created = 0
    files_created = 0
    try:
        os.makedirs(target, exist_ok=True)
        folders_created += 1
        for folder in template.get("folders", []):
            os.makedirs(os.path.join(target, folder), exist_ok=True)
            folders_created += 1
        for fname, content in template.get("files", {}).items():
            fpath = os.path.join(target, fname)
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(content)
            files_created += 1
        return {
            "path": target,
            "template": template_id,
            "folders_created": folders_created,
            "files_created": files_created,
            "message": f"Created '{name}' from {template_id} template.",
        }
    except Exception as e:
        return {"error": str(e)}


class SorterAPI(BaseHTTPRequestHandler):
    
    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
    
    def _json(self, data, status=200):
        self.send_response(status)
        self._cors()
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode())
    
    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()
    
    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        
        # Serve the GUI
        if parsed.path in ('/', '/index.html', ''):
            gui_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'index.html')
            if os.path.exists(gui_path):
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.end_headers()
                with open(gui_path, 'rb') as f:
                    self.wfile.write(f.read())
                return

        # Serve Simple Mode
        if parsed.path in ('/simple', '/simple.html'):
            simple_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'simple.html')
            if os.path.exists(simple_path):
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.end_headers()
                with open(simple_path, 'rb') as f:
                    self.wfile.write(f.read())
                return
        
        if parsed.path == '/api/health':
            self._json({
                'ok': True,
                'app': 'River FIS',
                'simple': '/simple',
                'advanced': '/',
            })
            return

        if parsed.path == '/api/scan':
            scan_path = params.get('path', [''])[0]
            top_only = params.get('top', ['false'])[0].lower() == 'true'
            use_nlp = params.get('nlp', ['false'])[0].lower() == 'true'
            
            if not scan_path or not os.path.exists(scan_path):
                self._json({'error': f'Path not found: {scan_path}'}, 404)
                return
            
            scan_id = start_scan(scan_path, mode='sort', top_only=top_only, use_nlp=use_nlp)
            try:
                results = classify_directory(
                    scan_path, use_nlp=use_nlp,
                    top_level_only=top_only
                )
            except Exception as exc:
                finish_scan(scan_id, 0, status='error', error=str(exc))
                self._json({'error': str(exc), 'scan_id': scan_id}, 500)
                return
            
            # Enrich with Markov predictions and naming
            engine = NamingEngine()
            enriched = []
            threshold = get_auto_approve_threshold()
            for r in results:
                entry = {
                    'filepath': r['filepath'],
                    'filename': r['filename'],
                    'ext': r['ext'],
                    'size': r['size'],
                    'baseline': clean_filename(r['filename']),
                    'domain': r['classification']['domain'],
                    'domain_code': r['classification']['code'],
                    'confidence': r['classification']['confidence'],
                    'source': r['classification'].get('source', 'yake'),
                    'matched': r['classification'].get('matched', []),
                    'keywords': [k['keyword'] for k in r.get('keywords', [])[:5]],
                    'text_preview': r.get('text_preview', '')[:100],
                }
                
                # Markov prediction
                mp = r.get('markov_prediction')
                if mp:
                    entry['markov'] = {
                        'domain': mp['domain'],
                        'confidence': mp['confidence'],
                        'training_size': mp.get('training_size', 0),
                    }
                    if mp.get('correction_warning'):
                        entry['markov']['warning'] = mp['correction_warning']
                
                # Auto-approve suggestion
                if entry['confidence'] >= threshold:
                    entry['auto_approve'] = True
                
                # Naming predictions — all presets
                file_info = {
                    'filename': r['filename'],
                    'ext': r['ext'],
                    'domain': r['classification']['domain'],
                    'domain_code': r['classification']['code'],
                    'keywords': [k['keyword'] for k in r.get('keywords', [])[:4]],
                }
                entry['names'] = {
                    'baseline': entry['baseline'],
                    'presets': engine.preview_all_presets(file_info),
                }

                cache_classification(scan_id, entry)
                enriched.append(entry)

            finish_scan(scan_id, len(enriched))
            
            self._json({
                'scan_id': scan_id,
                'cached': True,
                'files': enriched,
                'total': len(enriched),
                'scan_path': scan_path,
                'auto_approve_threshold': threshold,
                'domains': list(DOMAIN_RULES.keys()),
            })
        
        elif parsed.path == '/api/stats':
            stats = get_engine_stats()
            self._json(stats)

        elif parsed.path == '/api/cache/status':
            self._json(cache_status())

        elif parsed.path == '/api/roots':
            if params.get('seed', ['false'])[0].lower() == 'true':
                seed_demo_roots()
            self._json({'roots': list_roots()})

        elif parsed.path == '/api/actions':
            limit = int(params.get('limit', ['50'])[0])
            self._json({'actions': recent_actions(limit=limit)})

        elif parsed.path == '/api/cache/files':
            limit = int(params.get('limit', ['100'])[0])
            root = params.get('root', [''])[0]
            query = params.get('q', [''])[0]
            ext = params.get('ext', [''])[0]
            self._json({'files': recent_cached_files(limit=limit, root=root, query=query, ext=ext)})

        elif parsed.path == '/api/cache/findings':
            root = params.get('root', [''])[0]
            scan_raw = params.get('scan_id', [''])[0]
            scan_id = int(scan_raw) if scan_raw else None
            limit = int(params.get('limit', ['50'])[0])
            self._json({'findings': recent_organization_findings(root=root, scan_id=scan_id, limit=limit)})

        elif parsed.path == '/api/findings':
            root = params.get('root', [''])[0]
            min_weight = int(params.get('min_weight', ['3'])[0])
            self._json(grouped_organization_findings(root=root, min_weight=min_weight))

        elif parsed.path == '/api/cache/summary':
            root = params.get('root', [''])[0]
            self._json(cached_folder_summary(root))

        elif parsed.path == '/api/cache/rename-plan':
            root = params.get('root', [''])[0]
            limit = int(params.get('limit', ['200'])[0])
            self._json(cached_rename_plan(root, limit=limit))

        elif parsed.path == '/api/cache/rename-sample':
            root = params.get('root', [''])[0]
            schema = params.get('schema', ['baseline'])[0]
            seed = int(params.get('seed', ['0'])[0])
            self._json(cached_rename_sample(root, schema=schema, seed=seed))

        elif parsed.path == '/api/cache/scan':
            scan_path = params.get('path', [''])[0]
            max_files = int(params.get('max', ['10000'])[0])
            recursive = params.get('recursive', ['true'])[0].lower() == 'true'
            follow_links = params.get('follow_links', ['false'])[0].lower() == 'true'
            compute_hash = params.get('hash', ['false'])[0].lower() in ('true', '1', 'yes', 'md5')
            self._json(scan_inventory(scan_path, max_files=max_files, recursive=recursive, follow_links=follow_links, compute_hash=compute_hash))

        elif parsed.path == '/api/cache/folder':
            folder_path = params.get('path', [''])[0]
            limit = int(params.get('limit', ['300'])[0])
            self._json(cached_folder_children(folder_path, limit=limit))

        elif parsed.path == '/api/cache/folderbrain':
            folder_path = params.get('path', [''])[0]
            write = params.get('write', ['false'])[0].lower() == 'true'
            result = write_folderbrain(folder_path) if write else folderbrain_summary(folder_path)
            self._json(result, 500 if result.get('error') else 200)

        elif parsed.path == '/api/cache/folderbrains':
            root = params.get('root', [''])[0]
            limit = int(params.get('limit', ['500'])[0])
            overwrite = params.get('overwrite', ['true'])[0].lower() == 'true'
            result = write_folderbrains(root, limit=limit, overwrite=overwrite)
            self._json(result, 500 if result.get('error_count') else 200)

        elif parsed.path == '/api/cache/clusters':
            root = params.get('root', [''])[0]
            min_folders = int(params.get('min_folders', ['2'])[0])
            limit = int(params.get('limit', ['12'])[0])
            self._json(cached_theme_clusters(root=root, min_folders=min_folders, limit=limit))

        elif parsed.path == '/api/folders/composition':
            root = params.get('root', [''])[0]
            extension = params.get('extension', ['html'])[0]
            threshold = params.get('threshold', ['60'])[0]
            max_folders = params.get('max_folders', ['400'])[0]
            max_files = params.get('max_files_per_folder', ['20000'])[0]
            exclude = params.get('exclude', [''])[0]
            result = folder_composition_scan(
                root,
                extension=extension,
                threshold=threshold,
                max_folders=max_folders,
                max_files_per_folder=max_files,
                exclude=exclude,
            )
            self._json(result, 500 if result.get('error') else 200)

        elif parsed.path == '/api/folders/compare':
            left = params.get('left', [''])[0]
            right = params.get('right', [''])[0]
            recursive = params.get('recursive', ['true'])[0].lower() == 'true'
            compare = params.get('compare', ['relative_path'])[0]
            max_files = params.get('max_files', ['50000'])[0]
            exclude = params.get('exclude', [''])[0]
            result = folder_compare_scan(
                left,
                right,
                recursive=recursive,
                compare=compare,
                max_files=max_files,
                exclude=exclude,
            )
            self._json(result, 500 if result.get('error') else 200)

        elif parsed.path == '/api/cache/classify':
            root = params.get('root', [''])[0]
            limit = int(params.get('limit', ['200'])[0])
            only_unclassified = params.get('only_unclassified', ['false'])[0].lower() == 'true'
            paths = cached_file_paths(root=root, limit=limit, only_unclassified=only_unclassified)
            action = record_action(
                'cache_classify',
                target_path=root,
                status='running',
                payload={'limit': limit, 'only_unclassified': only_unclassified, 'cached_paths': len(paths)},
            )
            scan_id = start_scan(root or 'cache', mode='cache_classify', top_only=False, use_nlp=False)
            engine = NamingEngine()
            enriched = []
            threshold = get_auto_approve_threshold()
            try:
                for fp in paths:
                    r = classify_file(fp, use_nlp=False, use_markov=True)
                    if 'error' in r:
                        continue
                    entry = {
                        'filepath': r['filepath'],
                        'filename': r['filename'],
                        'ext': r['ext'],
                        'size': r['size'],
                        'baseline': clean_filename(r['filename']),
                        'domain': r['classification']['domain'],
                        'domain_code': r['classification']['code'],
                        'confidence': r['classification']['confidence'],
                        'source': r['classification'].get('source', 'yake'),
                        'matched': r['classification'].get('matched', []),
                        'keywords': [k['keyword'] for k in r.get('keywords', [])[:5]],
                        'text_preview': r.get('text_preview', '')[:100],
                    }
                    mp = r.get('markov_prediction')
                    if mp:
                        entry['markov'] = {
                            'domain': mp['domain'],
                            'confidence': mp['confidence'],
                            'training_size': mp.get('training_size', 0),
                        }
                        if mp.get('correction_warning'):
                            entry['markov']['warning'] = mp['correction_warning']
                    if entry['confidence'] >= threshold:
                        entry['auto_approve'] = True
                    file_info = {
                        'filename': r['filename'],
                        'ext': r['ext'],
                        'domain': r['classification']['domain'],
                        'domain_code': r['classification']['code'],
                        'keywords': [k['keyword'] for k in r.get('keywords', [])[:4]],
                    }
                    entry['names'] = {
                        'baseline': entry['baseline'],
                        'presets': engine.preview_all_presets(file_info),
                    }
                    cache_classification(scan_id, entry)
                    enriched.append(entry)
                finish_scan(scan_id, len(enriched))
            except Exception as exc:
                finish_scan(scan_id, len(enriched), status='error', error=str(exc))
                update_action_status(action['action_id'], 'error', {'scan_id': scan_id, 'classified': len(enriched)}, str(exc))
                self._json({'error': str(exc), 'scan_id': scan_id}, 500)
                return
            update_action_status(action['action_id'], 'complete', {'scan_id': scan_id, 'classified': len(enriched)})
            self._json({
                'action_code': action['action_code'],
                'scan_id': scan_id,
                'files': enriched,
                'total': len(enriched),
                'root': root,
                'auto_approve_threshold': threshold,
            })
        
        elif parsed.path == '/api/predict':
            keywords = params.get('keywords', [''])[0].split(',')
            ext = params.get('ext', [''])[0]
            prediction = predict_domain(keywords, ext)
            self._json(prediction or {'error': 'Not enough training data'})
        
        elif parsed.path == '/api/domains':
            self._json({
                'domains': {k: v['code'] for k, v in DOMAIN_RULES.items()}
            })

        elif parsed.path == '/api/hub/status':
            self._json(hub_status())

        elif parsed.path == '/api/organizer/preview':
            scan_path = params.get('path', [''])[0]
            max_files = int(params.get('max', ['50'])[0])
            self._json(organizer_preview(scan_path, max_files=max_files))

        elif parsed.path == '/api/rename/preview':
            scan_path = params.get('path', [''])[0]
            max_files = int(params.get('max', ['50'])[0])
            self._json(rename_preview(scan_path, max_files=max_files))

        elif parsed.path == '/api/rename/baseline-plan':
            scan_path = params.get('path', [''])[0]
            max_files = int(params.get('max', ['200'])[0])
            self._json(baseline_rename_plan(scan_path, max_files=max_files))

        elif parsed.path == '/api/manual/scan':
            scan_path = params.get('path', [''])[0]
            result = manual_scan(scan_path)
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except json.JSONDecodeError:
                    result = {'error': result}
            self._json(result)
        
        else:
            self._json({'error': 'Not found'}, 404)
    
    def do_POST(self):
        content_len = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(content_len)) if content_len else {}
        parsed = urlparse(self.path)
        
        if parsed.path == '/api/findings/decide':
            finding_id = body.get('finding_id')
            result = decide_organization_finding(
                int(finding_id) if finding_id else None,
                body.get('action', 'defer'),
                schema=body.get('schema', 'baseline'),
                payload=body,
            )
            self._json(result, 500 if result.get('error') else 200)
            return

        if parsed.path == '/api/decide':
            # Record a batch of decisions
            decisions = body.get('decisions', [])
            if not decisions:
                self._json({'error': 'No decisions provided'}, 400)
                return
            
            recorded = 0
            action = record_action(
                'decision_batch',
                status='running',
                payload={'requested': len(decisions)},
            )
            for d in decisions:
                try:
                    record_decision(
                        filename=d['filename'],
                        extension=d.get('ext', ''),
                        keywords=d.get('keywords', []),
                        proposed_domain=d.get('proposed_domain', 'UNCATEGORIZED'),
                        final_domain=d.get('final_domain', d.get('proposed_domain', 'UNCATEGORIZED')),
                        confidence=d.get('confidence', 0),
                        action=d.get('action', 'approve'),
                        source=d.get('source', 'yake'),
                    )
                    cache_decision(d)
                    recorded += 1
                except Exception as e:
                    print(f"  Error recording decision: {e}")
            
            stats = get_engine_stats()
            update_action_status(action['action_id'], 'complete', {'recorded': recorded})
            self._json({
                'action_code': action['action_code'],
                'recorded': recorded,
                'total_decisions': stats['total_decisions'],
                'accuracy': stats['accuracy'],
                'auto_approve_threshold': stats['auto_approve_threshold'],
            })
        
        elif parsed.path == '/api/nlp-classify':
            # Run NLP on specific files
            filepaths = body.get('files', [])
            results = []
            for fp in filepaths:
                r = classify_file(fp, use_nlp=True, use_markov=True)
                if 'error' not in r:
                    results.append({
                        'filepath': r['filepath'],
                        'filename': r['filename'],
                        'domain_code': r['classification'].get('code'),
                        'domain': r['classification']['domain'],
                        'confidence': r['classification']['confidence'],
                        'source': r['classification'].get('source', 'yake'),
                        'nlp_result': r.get('nlp_result'),
                        'nlp_summary': r.get('nlp_summary'),
                    })
                    cache_nlp_result(results[-1])
            self._json({'results': results})

        elif parsed.path == '/api/fis/classify-text':
            self._json(fis_text_classify(body.get('text', '')))

        elif parsed.path == '/api/create/folder':
            parent = body.get('parent', '')
            name = body.get('name', 'new-folder')
            template = body.get('template', 'empty')
            if not parent or not os.path.isdir(parent):
                self._json({'error': f'Parent folder not found: {parent}'}, 404)
                return
            result = create_from_template(parent, name, template)
            self._json(result)
        
        else:
            self._json({'error': 'Not found'}, 404)
    
    def log_message(self, format, *args):
        print(f"  [API] {args[0]}")


def main():
    init_db()
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8450
    server = ThreadingHTTPServer(('127.0.0.1', port), SorterAPI)
    print(f"\n  File Sorter API running on http://127.0.0.1:{port}")
    print(f"  Simple Mode: http://127.0.0.1:{port}/simple")
    print(f"  Advanced:    http://127.0.0.1:{port}/")
    print(f"  Endpoints: /api/scan, /api/decide, /api/stats, /api/nlp-classify, /api/predict")
    print(f"             /api/cache/status, /api/cache/files, /api/cache/scan, /api/cache/folder")
    print(f"             /api/hub/status, /api/organizer/preview, /api/rename/preview")
    print(f"             /api/rename/baseline-plan, /api/manual/scan, /api/fis/classify-text")
    print(f"  Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Shutting down.")
        server.shutdown()


if __name__ == '__main__':
    main()
