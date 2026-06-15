"""Naming Engine — configurable file naming from .sortconfig.yaml templates.

The user picks a preset or builds a custom pattern from tokens:
  {date} {domain} {slug} {seq} {version} {author} {ext} {cluster} {session}

Each token is filled by the classification + clustering pipeline.
"""

import re
import yaml
import os
from datetime import datetime
from pathlib import Path
from typing import Optional


DEFAULT_TEMPLATE = "{domain}_{slug}_{seq}.{ext}"

PRESETS = {
    'domain_first':    "{domain}_{slug}_{seq}.{ext}",
    'date_first':      "{date}_{slug}_{domain}.{ext}",
    'johnny_hybrid':   "{domain}.{seq} {slug}.{ext}",
    'research':        "{domain}_{slug}_v{version}_{date}.{ext}",
    'session_based':   "{date}_{session}_{slug}.{ext}",
    'minimal':         "{slug}.{ext}",
    'master_equation': "{chi}__{entity}__{state}__{date}__{shortcode}.{ext}",
}


def load_config(folder: str) -> dict:
    """Load .sortconfig.yaml from folder or any parent folder."""
    path = Path(folder)
    while path != path.parent:
        config_file = path / '.sortconfig.yaml'
        if config_file.exists():
            with open(config_file, 'r') as f:
                return yaml.safe_load(f)
        path = path.parent
    return {}


def slugify(text: str, case: str = 'kebab', max_words: int = 4) -> str:
    """Convert text to a filename-safe slug.
    
    UNIVERSAL BASELINE: always lowercase, always hyphens, no spaces.
    This is the floor — every naming preset builds on this.
    """
    # Remove special chars, keep alphanumeric and spaces
    clean = re.sub(r'[^a-zA-Z0-9\s]', '', text)
    words = clean.split()[:max_words]
    
    if not words:
        return 'unnamed'
    
    # BASELINE: always lowercase, always hyphens
    return '-'.join(w.lower() for w in words)


class NamingEngine:
    """Generates filenames from templates and classification data."""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        naming = self.config.get('naming', {})
        
        # Template
        preset = naming.get('active_preset', 'domain_first')
        presets = naming.get('presets', PRESETS)
        self.template = naming.get('template') or presets.get(preset, DEFAULT_TEMPLATE)
        
        # Format options
        fmt = naming.get('format', {})
        self.date_format = fmt.get('date', 'YYYYMMDD')
        self.slug_case = fmt.get('slug_case', 'kebab')
        self.slug_max_words = fmt.get('slug_max_words', 4)
        self.seq_digits = fmt.get('seq_digits', 4)
        self.separator = fmt.get('separator', '_')
        self.lowercase_ext = fmt.get('lowercase_ext', True)
        
        # Sequence counters per domain
        self._seq_counters = {}
    
    def _format_date(self, dt: datetime = None) -> str:
        """Format date according to config."""
        dt = dt or datetime.now()
        if self.date_format == 'YYYYMMDD':
            return dt.strftime('%Y%m%d')
        elif self.date_format == 'YYYY-MM-DD':
            return dt.strftime('%Y-%m-%d')
        elif self.date_format == 'MM-DD-YYYY':
            return dt.strftime('%m-%d-%Y')
        return dt.strftime('%Y%m%d')
    
    def next_seq(self, domain: str) -> str:
        """Get next sequence number for a domain."""
        self._seq_counters[domain] = self._seq_counters.get(domain, 0) + 1
        return str(self._seq_counters[domain]).zfill(self.seq_digits)
    
    def generate(self, file_info: dict) -> str:
        """Generate a filename from classification data.
        
        file_info should contain:
          filename: original filename
          ext: extension
          domain: classified domain
          domain_code: short code (TP, DV, etc.)
          keywords: list of keyword strings
          version: optional version number
          author: optional author
          cluster: optional cluster name
          session: optional session ID
          date: optional datetime
        """
        ext = file_info.get('ext', '').lstrip('.')
        if self.lowercase_ext:
            ext = ext.lower()
        
        domain_code = file_info.get('domain_code', 'UC')
        keywords = file_info.get('keywords', [])
        
        # Build slug from keywords or filename
        if keywords:
            slug_source = ' '.join(keywords[:self.slug_max_words])
        else:
            slug_source = Path(file_info.get('filename', 'unnamed')).stem
        slug = slugify(slug_source, self.slug_case, self.slug_max_words)
        
        # Token values
        tokens = {
            'date': self._format_date(file_info.get('date')),
            'domain': domain_code,
            'slug': slug,
            'seq': self.next_seq(domain_code),
            'version': str(file_info.get('version', 1)).zfill(2),
            'author': file_info.get('author', ''),
            'ext': ext,
            'cluster': slugify(file_info.get('cluster', ''), self.slug_case, 2),
            'session': file_info.get('session', ''),
        }
        
        # Fill template
        result = self.template
        for key, val in tokens.items():
            result = result.replace('{' + key + '}', str(val))
        
        # Clean up: remove empty tokens, double separators
        result = re.sub(r'[_\-]{2,}', self.separator, result)
        result = result.strip('_- ')
        
        return result
    
    def preview_all_presets(self, file_info: dict) -> dict:
        """Show what the filename would look like under every preset."""
        results = {}
        original_template = self.template
        
        for name, template in PRESETS.items():
            self.template = template
            # Reset seq counter for preview
            domain_code = file_info.get('domain_code', 'UC')
            self._seq_counters[domain_code] = self._seq_counters.get(domain_code, 0)
            results[name] = self.generate(file_info)
        
        self.template = original_template
        return results


def preview_naming(files: list, config: dict = None) -> list:
    """Preview naming for a batch of classified files.
    Returns ALL preset predictions per file for the GUI.
    """
    engine = NamingEngine(config)
    
    previews = []
    for f in files:
        file_info = {
            'filename': f.get('filename', ''),
            'ext': f.get('ext', ''),
            'domain': f.get('classification', {}).get('domain', 'UNCATEGORIZED'),
            'domain_code': f.get('classification', {}).get('code', 'UC'),
            'keywords': [k['keyword'] for k in f.get('keywords', [])],
        }
        
        # Baseline clean: lowercase + hyphens, no smart naming
        baseline = clean_filename(file_info['filename'])
        
        # All preset predictions
        all_presets = engine.preview_all_presets(file_info)
        
        previews.append({
            'original': f.get('filename', ''),
            'filepath': f.get('filepath', ''),
            'baseline': baseline,
            'presets': all_presets,
        })
    
    return previews


def clean_filename(filename: str) -> str:
    """Universal baseline cleaner.
    
    ALWAYS: lowercase, hyphens between words, no spaces, no special chars.
    This is the minimum — applied even if no classification runs.
    """
    path = Path(filename)
    ext = path.suffix.lower()
    stem = path.stem
    
    # Replace underscores, spaces, dots (not extension), camelCase splits
    clean = re.sub(r'([a-z])([A-Z])', r'\1 \2', stem)  # camelCase
    clean = re.sub(r'[_\s.]+', '-', clean)               # separators → hyphens
    clean = re.sub(r'[^a-zA-Z0-9\-]', '', clean)         # strip special chars
    clean = re.sub(r'-+', '-', clean)                     # collapse double hyphens
    clean = clean.strip('-').lower()
    
    if not clean:
        clean = 'unnamed'
    
    return f"{clean}{ext}"
