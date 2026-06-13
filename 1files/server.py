# -*- coding: utf-8 -*-
"""
Organize Server - Lightweight file organizer backend
Run: python server.py | Serves on 0.0.0.0:8500
"""
import json, os, hashlib
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote
from pathlib import Path
from collections import defaultdict

PORT = 8500
HTML_DIR = os.path.dirname(os.path.abspath(__file__))

EXT_MAP = {
    "Documents": [".pdf",".doc",".docx",".txt",".md",".rtf",".odt",".epub"],
    "Spreadsheets": [".xlsx",".xls",".csv",".tsv",".xlsm"],
    "Images": [".png",".jpg",".jpeg",".gif",".bmp",".svg",".webp",".ico",".tif",".tiff"],
    "Audio": [".mp3",".wav",".m4a",".flac",".aac",".ogg",".wma"],
    "Video": [".mp4",".mkv",".avi",".mov",".wmv",".webm",".flv"],
    "Code": [".py",".js",".ts",".jsx",".tsx",".html",".css",".json",".yml",".yaml",".toml",".rs",".go",".java",".cpp",".c",".h",".lean"],
    "Archives": [".zip",".rar",".7z",".tar",".gz",".bz2"],
    "PowerPoint": [".pptx",".ppt"],
    "Data": [".sql",".db",".sqlite",".jsonl",".parquet"],
}

def get_type(ext):
    ext = ext.lower()
    for cat, exts in EXT_MAP.items():
        if ext in exts:
            return cat
    return "Other"

def fmt_size(b):
    for u in ["B","KB","MB","GB","TB"]:
        if b < 1024:
            return f"{b:.1f} {u}"
        b /= 1024
    return f"{b:.1f} PB"

def scan_folder(root):
    root = Path(root)
    if not root.exists():
        return {"error": f"Not found: {root}"}
    by_type = defaultdict(lambda: {"count": 0, "size": 0, "exts": defaultdict(int)})
    empty = []
    files = []
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(root):
        depth = str(dirpath).replace(str(root), "").count(os.sep)
        if depth > 10:
            dirnames.clear()
            continue
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        if not filenames and not dirnames:
            empty.append(str(dirpath))
        for f in filenames:
            fp = os.path.join(dirpath, f)
            try:
                sz = os.path.getsize(fp)
                mt = os.path.getmtime(fp)
            except:
                continue
            ext = os.path.splitext(f)[1]
            cat = get_type(ext)
            by_type[cat]["count"] += 1
            by_type[cat]["size"] += sz
            by_type[cat]["exts"][ext.lower()] += 1
            total_size += sz
            files.append({"name": f, "path": str(dirpath), "size": sz, "modified": mt, "type": cat, "ext": ext.lower()})
    files.sort(key=lambda x: x["size"], reverse=True)
    largest = [{"name": f["name"], "path": f["path"], "size": fmt_size(f["size"]), "raw": f["size"]} for f in files[:20]]
    bt = {}
    for k, v in sorted(by_type.items(), key=lambda x: x[1]["size"], reverse=True):
        bt[k] = {"count": v["count"], "size": fmt_size(v["size"]), "raw": v["size"], "exts": dict(v["exts"])}
    return {
        "path": str(root), "total_files": len(files), "total_size": fmt_size(total_size),
        "total_raw": total_size, "by_type": bt, "empty_folders": empty[:100],
        "empty_count": len(empty), "largest": largest,
    }

def find_duplicates(root):
    root = Path(root)
    size_map = defaultdict(list)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for f in filenames:
            fp = os.path.join(dirpath, f)
            try:
                sz = os.path.getsize(fp)
            except:
                continue
            if sz > 0:
                size_map[sz].append(fp)
    dupes = []
    for sz, paths in size_map.items():
        if len(paths) < 2:
            continue
        hash_map = defaultdict(list)
        for p in paths:
            try:
                h = hashlib.md5()
                with open(p, "rb") as fh:
                    h.update(fh.read(65536))
                hash_map[h.hexdigest()].append(p)
            except:
                continue
        for h, hpaths in hash_map.items():
            if len(hpaths) >= 2:
                dupes.append({"hash": h, "size": fmt_size(sz), "raw": sz, "files": hpaths})
    dupes.sort(key=lambda x: x["raw"], reverse=True)
    wasted = sum(d["raw"] * (len(d["files"]) - 1) for d in dupes)
    return {"groups": dupes[:200], "total_groups": len(dupes), "wasted": fmt_size(wasted)}

def compare_folders(src, dst):
    def index_folder(p):
        idx = {}
        for dirpath, _, filenames in os.walk(p):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                rel = os.path.relpath(fp, p)
                try:
                    sz = os.path.getsize(fp)
                except:
                    continue
                idx[rel] = {"size": sz, "path": fp}
        return idx
    si, di = index_folder(src), index_folder(dst)
    identical, only_src, only_dst, different = [], [], [], []
    for rel, info in si.items():
        if rel in di:
            if info["size"] == di[rel]["size"]:
                identical.append({"file": rel, "size": fmt_size(info["size"])})
            else:
                different.append({"file": rel, "src_size": fmt_size(info["size"]), "dst_size": fmt_size(di[rel]["size"])})
        else:
            only_src.append({"file": rel, "size": fmt_size(info["size"])})
    for rel in di:
        if rel not in si:
            only_dst.append({"file": rel, "size": fmt_size(di[rel]["size"])})
    return {
        "identical": len(identical), "only_src": len(only_src), "only_dst": len(only_dst), "different": len(different),
        "identical_files": identical[:100], "only_src_files": only_src[:100], "only_dst_files": only_dst[:100], "different_files": different[:50],
    }

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *a):
        pass

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self._cors()
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        p = urlparse(self.path)
        if p.path in ("/", "/index.html"):
            try:
                with open(os.path.join(HTML_DIR, "index.html"), "rb") as f:
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html")
                    self.end_headers()
                    self.wfile.write(f.read())
            except:
                self._json({"error": "index.html not found"}, 404)
        elif p.path == "/api/scan":
            q = parse_qs(p.query)
            folder = unquote(q.get("path", [""])[0])
            if not folder:
                return self._json({"error": "path required"}, 400)
            self._json(scan_folder(folder))
        elif p.path == "/api/duplicates":
            q = parse_qs(p.query)
            folder = unquote(q.get("path", [""])[0])
            if not folder:
                return self._json({"error": "path required"}, 400)
            self._json(find_duplicates(folder))
        elif p.path == "/api/compare":
            q = parse_qs(p.query)
            src = unquote(q.get("src", [""])[0])
            dst = unquote(q.get("dst", [""])[0])
            if not src or not dst:
                return self._json({"error": "src and dst required"}, 400)
            self._json(compare_folders(src, dst))
        elif p.path == "/api/ls":
            q = parse_qs(p.query)
            folder = unquote(q.get("path", [""])[0]) or "C:\\"
            try:
                items = []
                for e in sorted(Path(folder).iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                    items.append({"name": e.name, "is_dir": e.is_dir(), "path": str(e)})
                self._json({"path": folder, "items": items[:500]})
            except Exception as ex:
                self._json({"error": str(ex)}, 400)
        else:
            self._json({"error": "not found"}, 404)

if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"\n  Organize Server on http://0.0.0.0:{PORT}")
    print(f"  Open: http://localhost:{PORT}\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()
