"""
Unified TTS Pipeline for Theophysics
=====================================
Master orchestrator that chains:
1. Text Normalization (numbers, measures, fractions, dates, money, etc.)
2. Theophysics Translation (Greek letters, χ-field symbols, equations, axiom refs)
3. TTS Engine Output (Edge TTS free / OpenAI TTS premium)

Usage:
    python tts_pipeline.py <input_file> <output_file> [--engine edge|openai] [--voice VOICE]

Author: David Lowe / Theophysics Project
"""

import os
import sys
import re
import argparse
import asyncio
from pathlib import Path
from typing import Optional, Tuple

# Add converters to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# ── Front-matter helpers ──────────────────────────────────────────────────────

def extract_front_matter(text: str) -> Tuple[Optional[str], str, dict]:
    """
    Parse YAML front-matter (--- ... ---) from markdown text.
    Returns (title, body_without_yaml, yaml_dict).
    title is taken from YAML 'title:' field, then first # H1, then None.
    """
    yaml_dict = {}
    body = text

    yaml_match = re.match(r'^---\s*\r?\n(.*?)\r?\n---\s*\r?\n', text, re.DOTALL)
    if yaml_match:
        yaml_raw = yaml_match.group(1)
        body = text[yaml_match.end():]
        for line in yaml_raw.splitlines():
            m = re.match(r'^(\w[\w\s]*):\s*(.+)', line.strip())
            if m:
                yaml_dict[m.group(1).strip().lower()] = m.group(2).strip().strip('"').strip("'")

    title = yaml_dict.get('title') or yaml_dict.get('Title')
    if not title:
        h1 = re.search(r'^\s*#\s+(.+)', body, re.MULTILINE)
        if h1:
            title = h1.group(1).strip()

    return title, body, yaml_dict


def sanitize_filename(name: str) -> str:
    """Convert a title to a safe filename (no special chars, max 80 chars)."""
    safe = re.sub(r'[<>:"/\\|?*\[\]]', '', name)
    safe = re.sub(r'\s+', '_', safe.strip())
    safe = re.sub(r'_+', '_', safe).strip('_')
    return safe[:80]


def make_clean_markdown(title: Optional[str], body: str) -> str:
    """Return clean markdown: YAML stripped, title as # H1, body below."""
    parts = []
    if title:
        parts.append(f"# {title}\n")
    parts.append(body.strip())
    return '\n'.join(parts)


def prepare_body_for_tts(body: str) -> str:
    """
    Remove metadata-heavy blocks that should remain in markdown but not be spoken.
    """
    text = body

    # Extract callouts and move them to an appendix for audio flow.
    lines = text.splitlines()
    kept_lines: list[str] = []
    callout_entries: list[str] = []
    i = 0
    while i < len(lines):
        start = re.match(r'^\s*>\s*\[!([^\]\s]+)\]\s*[-+]?\s*(.*)$', lines[i], flags=re.IGNORECASE)
        if not start:
            kept_lines.append(lines[i])
            i += 1
            continue

        ctype = start.group(1).strip().lower()
        chead = start.group(2).strip()
        content_lines: list[str] = []
        i += 1
        while i < len(lines) and re.match(r'^\s*>', lines[i]):
            content_lines.append(re.sub(r'^\s*>\s?', '', lines[i]).strip())
            i += 1

        content_lines = [ln for ln in content_lines if ln]
        cbody = " ".join(content_lines).strip()

        # Skip reader navigation/info callouts in TTS (too noisy).
        if ctype == "info" and ("read" in chead.lower() or "listen" in chead.lower()):
            continue

        entry_parts = [f"{ctype.capitalize()} callout"]
        if chead:
            entry_parts.append(chead)
        if cbody:
            entry_parts.append(cbody)
        callout_entries.append(". ".join(entry_parts).strip() + ".")

    text = "\n".join(kept_lines)

    text = re.sub(
        r'<!--\s*TSNS STRUCTURE START\s*-->.*?<!--\s*SEMANTIC INLINE LABELS END\s*-->',
        '',
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    text = re.sub(
        r'<details[^>]*>.*?</details>',
        '',
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    text = re.sub(
        r'>\s*\[!info\]-\s*📖\s*Read\s*&\s*Listen.*?(?:\n\s*\n|---\s*\n)',
        '\n\n',
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )

    # Convert markdown tables to natural speech.
    def _table_to_speech(block: str) -> str:
        lines = [ln.strip() for ln in block.strip().splitlines() if ln.strip()]
        if len(lines) < 2:
            return block
        if "|" not in lines[0] or "|" not in lines[1]:
            return block
        if not re.search(r'^\|?[\s:\-|\t]+\|?$', lines[1]):
            return block

        def _cells(ln: str):
            parts = [c.strip() for c in ln.strip().strip("|").split("|")]
            return [c for c in parts if c != ""]

        headers = _cells(lines[0])
        rows = [_cells(ln) for ln in lines[2:]]
        if not headers:
            return block

        out = ["", "Table follows."]
        for i, row in enumerate(rows, start=1):
            pairs = []
            for idx, val in enumerate(row):
                hdr = headers[idx] if idx < len(headers) else f"column {idx + 1}"
                if val:
                    pairs.append(f"{hdr}: {val}")
            if pairs:
                out.append(f"Row {i}. " + "; ".join(pairs) + ".")
        out.append("End table.")
        out.append("")
        return "\n".join(out)

    table_block_pattern = re.compile(r'((?:^\s*\|.*\|\s*$\n?){2,})', flags=re.MULTILINE)
    text = table_block_pattern.sub(lambda m: _table_to_speech(m.group(1)), text)

    # Remove heading hash markers so TTS does not say "hashtag".
    text = re.sub(r'^\s{0,3}#{1,6}\s+(.*)$', r'\1', text, flags=re.MULTILINE)

    # Keep callout content but remove marker syntax.
    text = re.sub(r'^\s*>\s*\[![^\]]+\].*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*>\s?', '', text, flags=re.MULTILINE)

    # Strip markdown link/image syntax while preserving readable text.
    text = re.sub(r'!\[[^\]]*\]\([^)]+\)', '', text)
    text = re.sub(r'!\[\[[^\]]+\]\]', '', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    text = re.sub(r'\[\[([^\]|]+)\|([^\]]+)\]\]', r'\2', text)
    text = re.sub(r'\[\[([^\]]+)\]\]', r'\1', text)

    # Remove Obsidian block anchors and anchor references.
    text = re.sub(r'#\^[A-Za-z0-9._-]+', '', text)
    text = re.sub(r'^\s*\^[A-Za-z0-9._-]+\s*$', '', text, flags=re.MULTILINE)

    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
    text = re.sub(r'</?[A-Za-z][^>]*>', '', text)
    text = re.sub(r'`{1,3}', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text).strip()

    if callout_entries:
        appendix_lines = [
            "",
            "Audio note. Detailed callouts are listed at the end of this narration.",
            "",
            "Callout appendix.",
        ]
        for idx, entry in enumerate(callout_entries, start=1):
            appendix_lines.append(f"Callout {idx}. {entry}")
        text = f"{text}\n\n" + "\n".join(appendix_lines)

    return text

# Import text normalizers
from theophysics_normalizer import normalize_for_tts as normalize_theophysics

# Try to import the standard converters
try:
    from converters.Cardinal import Cardinal
    from converters.Ordinal import Ordinal
    from converters.Decimal import Decimal
    from converters.Fraction import Fraction
    from converters.Measure import Measure
    from converters.Money import Money
    from converters.Date import Date
    from converters.Time import Time
    from converters.Telephone import Telephone
    from converters.Electronic import Electronic
    CONVERTERS_AVAILABLE = True
except ImportError as e:
    print(f"[WARNING] Standard converters not fully available: {e}")
    print("[INFO] Install singleton_decorator: pip install singleton-decorator")
    CONVERTERS_AVAILABLE = False


class TextNormalizer:
    """
    Combines standard TTS normalization with Theophysics-specific handling.
    """
    
    def __init__(self):
        if CONVERTERS_AVAILABLE:
            self.cardinal = Cardinal()
            self.ordinal = Ordinal()
            self.decimal = Decimal()
            self.fraction = Fraction()
            self.measure = Measure()
            self.money = Money()
            self.date = Date()
            self.time = Time()
            self.telephone = Telephone()
            self.electronic = Electronic()
        
        # Patterns for detection
        self.patterns = {
            'money': re.compile(r'[\$€£¥]\s*[\d,]+(?:\.\d+)?|\d+(?:\.\d+)?\s*(?:dollars?|euros?|pounds?|yen|cents?)'),
            'measure': re.compile(r'\d+(?:\.\d+)?\s*(?:km|m|cm|mm|mi|ft|in|kg|g|mg|lb|oz|L|mL|gal|mph|kph|Hz|kHz|MHz|GHz|W|kW|MW|V|A|Ω|°[CF]?)'),
            'fraction': re.compile(r'\d+\s*/\s*\d+|[½⅓⅔¼¾⅕⅖⅗⅘⅙⅚⅐⅛⅜⅝⅞⅑⅒]'),
            'decimal': re.compile(r'-?\d+\.\d+'),
            'ordinal': re.compile(r'\b(\d+)(st|nd|rd|th)\b', re.IGNORECASE),
            'date': re.compile(r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s*\d{4}\b', re.IGNORECASE),
            'time': re.compile(r'\b\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM|am|pm)?\b'),
            'telephone': re.compile(r'(?:\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'),
            'cardinal': re.compile(r'\b\d+\b'),
        }

    def normalize_numbers(self, text: str) -> str:
        """Apply standard number/measure/date conversions."""
        if not CONVERTERS_AVAILABLE:
            return text
        
        # Process in order of specificity (most specific first)
        
        # Money: $100.50 -> one hundred dollars and fifty cents
        def replace_money(match):
            try:
                return ' ' + self.money.convert(match.group(0)) + ' '
            except:
                return match.group(0)
        text = self.patterns['money'].sub(replace_money, text)
        
        # Measures: 5.2 km -> five point two kilometers
        def replace_measure(match):
            try:
                return ' ' + self.measure.convert(match.group(0)) + ' '
            except:
                return match.group(0)
        text = self.patterns['measure'].sub(replace_measure, text)
        
        # Fractions: 1/2 -> one half
        def replace_fraction(match):
            try:
                return ' ' + self.fraction.convert(match.group(0)) + ' '
            except:
                return match.group(0)
        text = self.patterns['fraction'].sub(replace_fraction, text)
        
        # Ordinals: 1st -> first
        def replace_ordinal(match):
            try:
                return ' ' + self.ordinal.convert(match.group(0)) + ' '
            except:
                return match.group(0)
        text = self.patterns['ordinal'].sub(replace_ordinal, text)
        
        # Decimals: 3.14 -> three point one four
        def replace_decimal(match):
            try:
                return ' ' + self.decimal.convert(match.group(0)) + ' '
            except:
                return match.group(0)
        text = self.patterns['decimal'].sub(replace_decimal, text)
        
        # Cardinals (last - catches remaining numbers): 42 -> forty two
        def replace_cardinal(match):
            try:
                return ' ' + self.cardinal.convert(match.group(0)) + ' '
            except:
                return match.group(0)
        text = self.patterns['cardinal'].sub(replace_cardinal, text)
        
        return text
    
    def normalize(self, text: str) -> str:
        """
        Full normalization pipeline:
        1. Standard number/measure normalization
        2. Theophysics-specific normalization
        3. Cleanup
        """
        # Step 1: Standard conversions
        text = self.normalize_numbers(text)
        
        # Step 2: Theophysics-specific (Greek, symbols, equations, axiom refs)
        text = normalize_theophysics(text)
        
        # Step 3: Final cleanup
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        return text


class TTSEngine:
    """
    Unified TTS engine interface supporting Edge TTS and OpenAI TTS.
    """
    
    def __init__(self, engine: str = 'edge', voice: Optional[str] = None, api_key: Optional[str] = None):
        self.engine = engine.lower()
        self.api_key = api_key or os.environ.get('OPENAI_API_KEY')
        
        # Default voices
        self.default_voices = {
            'edge': 'en-US-BrianMultilingualNeural',
            'openai': 'onyx'
        }
        self.voice = voice or self.default_voices.get(self.engine, 'en-US-BrianMultilingualNeural')

    async def synthesize_edge(self, text: str, output_path: str) -> bool:
        """Synthesize using Edge TTS (free)."""
        try:
            import edge_tts
        except ImportError:
            print("[ERROR] edge-tts not installed. Run: pip install edge-tts")
            return False
        
        try:
            communicate = edge_tts.Communicate(text, self.voice)
            await communicate.save(output_path)
            return True
        except Exception as e:
            print(f"[ERROR] Edge TTS failed: {e}")
            return False
    
    def synthesize_openai(self, text: str, output_path: str) -> bool:
        """Synthesize using OpenAI TTS (premium quality)."""
        if not self.api_key:
            print("[ERROR] OpenAI API key not set. Set OPENAI_API_KEY environment variable.")
            return False
        
        try:
            from openai import OpenAI
        except ImportError:
            print("[ERROR] openai not installed. Run: pip install openai")
            return False
        
        try:
            client = OpenAI(api_key=self.api_key)
            
            # OpenAI TTS has a 4096 character limit, so we need to chunk
            max_chunk = 4000
            chunks = [text[i:i+max_chunk] for i in range(0, len(text), max_chunk)]
            
            if len(chunks) == 1:
                # Single chunk - direct output
                response = client.audio.speech.create(
                    model="tts-1-hd",
                    voice=self.voice,
                    input=text
                )
                response.stream_to_file(output_path)
            else:
                # Multiple chunks - need to concatenate
                from pydub import AudioSegment
                combined = AudioSegment.empty()
                
                for i, chunk in enumerate(chunks):
                    print(f"  Processing chunk {i+1}/{len(chunks)}...")
                    temp_path = f"{output_path}.chunk{i}.mp3"
                    response = client.audio.speech.create(
                        model="tts-1-hd",
                        voice=self.voice,
                        input=chunk
                    )
                    response.stream_to_file(temp_path)
                    combined += AudioSegment.from_mp3(temp_path)
                    os.remove(temp_path)
                
                combined.export(output_path, format="mp3")
            
            return True
        except Exception as e:
            print(f"[ERROR] OpenAI TTS failed: {e}")
            return False
    
    async def synthesize(self, text: str, output_path: str) -> bool:
        """Main synthesis method - routes to appropriate engine."""
        if self.engine == 'edge':
            return await self.synthesize_edge(text, output_path)
        elif self.engine == 'openai':
            return self.synthesize_openai(text, output_path)
        else:
            print(f"[ERROR] Unknown engine: {self.engine}")
            return False


class TTSPipeline:
    """
    Complete TTS pipeline combining normalization and synthesis.
    """
    
    def __init__(self,
                 engine: str = 'edge',
                 voice: Optional[str] = None,
                 api_key: Optional[str] = None,
                 prelude: Optional[str] = None,
                 name_replacements: Optional[dict] = None):
        self.normalizer = TextNormalizer()
        self.tts = TTSEngine(engine=engine, voice=voice, api_key=api_key)
        self.prelude = prelude if prelude is not None else os.environ.get("THEOPHYSICS_TTS_PRELUDE", "")
        self.name_replacements = name_replacements or self._load_replacements_from_env()
    
    def read_input(self, input_path: str) -> str:
        """Read input file (supports .txt and .md)."""
        with open(input_path, 'r', encoding='utf-8') as f:
            return f.read()

    def _load_replacements_from_env(self) -> dict:
        """
        Load replacement pairs from env var:
        TTS_NAME_REPLACEMENTS='David=Author;David Lowe=The Author'
        """
        raw = os.environ.get("TTS_NAME_REPLACEMENTS", "").strip()
        if not raw:
            return {}
        replacements = {}
        for chunk in raw.split(";"):
            chunk = chunk.strip()
            if not chunk or "=" not in chunk:
                continue
            src, dst = chunk.split("=", 1)
            src = src.strip()
            dst = dst.strip()
            if src:
                replacements[src] = dst
        return replacements

    def _apply_name_replacements(self, text: str) -> str:
        if not self.name_replacements:
            return text
        out = text
        # Longer keys first avoids partial replacements consuming full names.
        for source in sorted(self.name_replacements.keys(), key=len, reverse=True):
            target = self.name_replacements[source]
            out = re.sub(re.escape(source), target, out, flags=re.IGNORECASE)
        return out

    async def process(self, input_path: str, output_path: str,
                      save_normalized: bool = False,
                      save_tts_txt: bool = True,
                      save_clean_md: bool = True) -> Tuple[bool, Optional[str]]:
        """
        Full pipeline:
        1. Read input — extract YAML title, strip front-matter
        2. Save clean .md  (YAML removed, title as # H1)
        3. Normalize text  (math translation, Greek, symbol conversion)
        4. Save TTS .txt   (what is fed to the voice engine)
        5. Synthesize .mp3 (named after the document title when possible)

        Returns (success, sanitized_title_or_None).
        output_path is used as the base directory + fallback stem when no title.
        """
        print(f"[PIPELINE] Processing: {input_path}")

        # ── Step 1: read & parse ──────────────────────────────────────────
        print("  [1/5] Reading input...")
        raw = self.read_input(input_path)
        print(f"        Raw length: {len(raw)} chars")

        title, body, _ = extract_front_matter(raw)
        if title:
            print(f"        Title: {title}")

        # Derive a title-based output stem
        out_p = Path(output_path)
        if title:
            safe_title = sanitize_filename(title)
            audio_path = str(out_p.parent / f"{safe_title}.mp3")
            tts_txt_path = str(out_p.parent / f"{safe_title}_tts.txt")
            clean_md_path = str(out_p.parent / f"{safe_title}_clean.md")
        else:
            audio_path = str(out_p.with_suffix('.mp3'))
            tts_txt_path = str(out_p.parent / f"{out_p.stem}_tts.txt")
            clean_md_path = str(out_p.parent / f"{out_p.stem}_clean.md")

        # ── Step 2: save clean markdown ───────────────────────────────────
        if save_clean_md:
            clean_md = make_clean_markdown(title, body)
            with open(clean_md_path, 'w', encoding='utf-8') as f:
                f.write(clean_md)
            print(f"  [2/5] Clean .md saved: {Path(clean_md_path).name}")
        else:
            print("  [2/5] Clean .md skipped")

        # ── Step 3: strip metadata-heavy blocks + normalize ───────────────
        print("  [3/5] Normalizing for TTS (math translation layer)...")
        body_for_tts = prepare_body_for_tts(body)
        normalized = self.normalizer.normalize(body_for_tts)
        print(f"        Normalized length: {len(normalized)} chars")

        # Optional prelude anchor so first spoken words are consistent.
        if self.prelude and self.prelude.strip():
            normalized = f"{self.prelude.strip()}. {normalized}".strip()

        # Optional name masking pass for publication-safe audio text.
        normalized = self._apply_name_replacements(normalized)

        # ── Step 4: save TTS text ─────────────────────────────────────────
        if save_tts_txt or save_normalized:
            with open(tts_txt_path, 'w', encoding='utf-8') as f:
                f.write(normalized)
            print(f"  [4/5] TTS text saved: {Path(tts_txt_path).name}")
        else:
            print("  [4/5] TTS text skipped")

        # ── Step 5: synthesize audio ──────────────────────────────────────
        print(f"  [5/5] Synthesizing audio ({self.tts.engine.upper()}, voice: {self.tts.voice})...")
        success = await self.tts.synthesize(normalized, audio_path)

        if success:
            print(f"[SUCCESS] Audio saved: {Path(audio_path).name}")
        else:
            print("[FAILED] Could not generate audio")

        return success, (sanitize_filename(title) if title else None)


async def main():
    parser = argparse.ArgumentParser(
        description='Theophysics Unified TTS Pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tts_pipeline.py input.md output.mp3
  python tts_pipeline.py input.txt output.mp3 --engine openai --voice nova
  python tts_pipeline.py input.md output.mp3 --engine edge --voice en-GB-SoniaNeural
  
Available Edge TTS voices (examples):
  en-US-BrianMultilingualNeural (default, male)
  en-US-JennyNeural (female)
  en-GB-SoniaNeural (British female)
  en-AU-NatashaNeural (Australian female)
  
Available OpenAI TTS voices:
  alloy, echo, fable, onyx (default), nova, shimmer
        """
    )
    
    parser.add_argument('input', help='Input file path (.txt or .md)')
    parser.add_argument('output', help='Output file path (.mp3)')
    parser.add_argument('--engine', '-e', choices=['edge', 'openai'], default='edge',
                       help='TTS engine to use (default: edge)')
    parser.add_argument('--voice', '-v', help='Voice name (engine-specific)')
    parser.add_argument('--api-key', '-k', help='OpenAI API key (or set OPENAI_API_KEY env var)')
    parser.add_argument('--save-normalized', '-s', action='store_true',
                       help='Save the normalized text to a file')
    parser.add_argument('--prelude', default='Faith Through Physics. Theophysics Vault. By David Lowe',
                       help='Optional spoken prelude prepended to TTS text')
    parser.add_argument('--replace-name', action='append', default=[],
                       help='Name replacement pair SOURCE=TARGET (repeatable)')
    
    args = parser.parse_args()
    
    # Validate input
    if not os.path.exists(args.input):
        print(f"[ERROR] Input file not found: {args.input}")
        sys.exit(1)
    
    # Create output directory if needed
    output_dir = os.path.dirname(args.output)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    replacements = {}
    for pair in args.replace_name:
        if "=" not in pair:
            print(f"[WARNING] Skipping invalid --replace-name '{pair}' (expected SOURCE=TARGET)")
            continue
        src, dst = pair.split("=", 1)
        src = src.strip()
        dst = dst.strip()
        if src:
            replacements[src] = dst

    # Run pipeline
    pipeline = TTSPipeline(
        engine=args.engine,
        voice=args.voice,
        api_key=args.api_key,
        prelude=args.prelude,
        name_replacements=replacements
    )
    
    success = await pipeline.process(
        args.input,
        args.output,
        save_normalized=args.save_normalized
    )
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    asyncio.run(main())
