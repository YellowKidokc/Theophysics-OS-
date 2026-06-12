"""Prepare papers for faiththruphysics.com publication."""
from __future__ import annotations
import json, os, re
from pathlib import Path

SITE_URL = os.environ.get("SITE_URL", "https://faiththruphysics.com")


def _extract_layer3(text: str) -> str:
    m = re.search(r"## Layer 3: The Paper\n(.*?)(\n## Layer 4:|$)", text, re.DOTALL)
    return (m.group(1).strip() if m else text)


def _extract_layer1(text: str) -> str:
    m = re.search(r"## Layer 1: Executive Summary\n(.*?)(\n## Layer 2:|$)", text, re.DOTALL)
    return (m.group(1).strip() if m else "")


def prepare(file_path: Path, out_dir: Path) -> dict:
    raw = file_path.read_text(encoding="utf-8", errors="replace")
    slug = file_path.stem.lower().replace(" ", "-")
    article = _extract_layer3(raw)
    summary = _extract_layer1(raw)
    laws = sorted(set(re.findall(r"\bL([1-9]|10)\b", raw)))
    law_badges = " ".join(f"<span style='border:1px solid #c9a227;padding:2px 6px'>L{l}</span>" for l in laws)
    html = f"""<html><head>
<link rel='canonical' href='{SITE_URL}/{slug}'>
<meta property='og:title' content='{file_path.stem}'>
<meta property='og:description' content='{summary[:180]}'>
<meta property='og:image' content='{SITE_URL}/{slug}_thumb.svg'>
</head><body style='background:#0d1117;color:#e6d5a8'>
<h1>{file_path.stem}</h1><div>{law_badges}</div><article>{article}</article>
</body></html>"""
    thumb = f"<svg xmlns='http://www.w3.org/2000/svg' width='1200' height='630'><rect width='100%' height='100%' fill='#0d1117'/><text x='50' y='120' fill='#c9a227' font-size='42'>{file_path.stem}</text><text x='50' y='200' fill='#e6d5a8'>Laws: {', '.join('L'+l for l in laws)}</text></svg>"
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / f"{slug}.html"; html_path.write_text(html, encoding="utf-8")
    thumb_path = out_dir / f"{slug}_thumb.svg"; thumb_path.write_text(thumb, encoding="utf-8")
    meta = {"slug": slug, "url": f"{SITE_URL}/{slug}", "laws": [f"L{l}" for l in laws], "title": file_path.stem}
    meta_path = out_dir / f"{slug}_meta.json"; meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return {"html": str(html_path), "thumb": str(thumb_path), "meta": str(meta_path)}


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    out = root / 'OUTPUT'
    results = [prepare(fp, out) for fp in (root / 'INPUT').glob('*.md')]
    (root / 'LOGS').mkdir(exist_ok=True)
    (root / 'LOGS' / 'prepare_log.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
