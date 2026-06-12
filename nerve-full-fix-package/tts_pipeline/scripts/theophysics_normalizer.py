"""
Theophysics Text Normalization Layer
=====================================
Converts Theophysics-specific symbols, equations, and notation to spoken form.
Designed to work with the TTS pipeline for the 188 Axiom Framework.

KEY BEHAVIOR:
- REMOVES YAML frontmatter (metadata at start of file).
- REMOVES code blocks (fenced ``` blocks).
- REMOVES images (markdown images and Obsidian embeds).
- CONVERTS markdown tables to narrative prose (data → story).
- REPLACES known LaTeX equations with spoken English from the Translation Table.
- SKIPS unknown LaTeX blocks ($$...$$ and $...$) - visual only.
- REMOVES links (markdown links, URLs, wikilinks).
- REMOVES hashtags (#tag).
- REMOVES inline code markers (keeps text).
- READS %%tts...%% blocks - human-written translations.
- Converts inline Greek letters, symbols, and axiom references.
- Optimizes numbers and formatting for TTS comprehension.

Author: David Lowe / Theophysics Project
"""

import re
import os
import pandas as pd
from typing import Dict, List, Tuple, Optional

# Optional AI fallback for equations not in master file
try:
    from ai_math_translator import AIMathTranslator
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False

class TheophysicsNormalizer:
    """
    Normalizes Theophysics-specific notation for TTS output.
    Handles: Greek letters, χ-field symbols, equations, axiom references, laws.
    """
    
    def __init__(self, ai_translator: Optional['AIMathTranslator'] = None):
        self.ai_translator = ai_translator
        
        # Greek letter pronunciations (lowercase)
        self.greek_lower = {
            'α': 'alpha', 'β': 'beta', 'γ': 'gamma', 'δ': 'delta',
            'ε': 'epsilon', 'ζ': 'zeta', 'η': 'eta', 'θ': 'theta',
            'ι': 'iota', 'κ': 'kappa', 'λ': 'lambda', 'μ': 'mu',
            'ν': 'nu', 'ξ': 'xi', 'ο': 'omicron', 'π': 'pi',
            'ρ': 'rho', 'σ': 'sigma', 'τ': 'tau', 'υ': 'upsilon',
            'φ': 'phi', 'χ': 'chi', 'ψ': 'psi', 'ω': 'omega',
            'ς': 'sigma'
        }
        
        # Greek letter pronunciations (uppercase)
        self.greek_upper = {
            'Α': 'Alpha', 'Β': 'Beta', 'Γ': 'Gamma', 'Δ': 'Delta',
            'Ε': 'Epsilon', 'Ζ': 'Zeta', 'Η': 'Eta', 'Θ': 'Theta',
            'Ι': 'Iota', 'Κ': 'Kappa', 'Λ': 'Lambda', 'Μ': 'Mu',
            'Ν': 'Nu', 'Ξ': 'Xi', 'Ο': 'Omicron', 'Π': 'Pi',
            'Ρ': 'Rho', 'Σ': 'Sigma', 'Τ': 'Tau', 'Υ': 'Upsilon',
            'Φ': 'Phi', 'Χ': 'Chi', 'Ψ': 'Psi', 'Ω': 'Omega'
        }
        
        # Theophysics-specific symbols
        self.theophysics_symbols = {
            'χ-field': 'chi field',
            '∞': 'infinity',
            '→': 'approaches',
            '←': 'comes from',
            '↔': 'is equivalent to',
            '⇒': 'implies',
            '⇔': 'if and only if',
            '≈': 'approximately equals',
            '≡': 'is identically equal to',
            '≠': 'is not equal to',
            '≤': 'is less than or equal to',
            '≥': 'is greater than or equal to',
            '℃': 'degrees Celsius',
            '℉': 'degrees Fahrenheit',
            '°': 'degrees',
        }
        
        self.special_letters = {
            '𝔰': 's',
            'ℏ': 'h-bar',
            'ℒ': 'L',
            '∂': 'partial',
        }
        
        self.subscripts = {
            '₀': ' sub zero ', '₁': ' sub one ', '₂': ' sub two ', 
            '₃': ' sub three ', '₄': ' sub four ', '₅': ' sub five ',
            '₆': ' sub six ', '₇': ' sub seven ', '₈': ' sub eight ', 
            '₉': ' sub nine ',
            'ₐ': ' sub a ', 'ₑ': ' sub e ', 'ₒ': ' sub o ', 
            'ₓ': ' sub x ', 'ᵢ': ' sub i ', 'ⱼ': ' sub j ', 
            'ₖ': ' sub k ', 'ₗ': ' sub l ', 'ₘ': ' sub m ', 
            'ₙ': ' sub n ', 'ₚ': ' sub p ', 'ₛ': ' sub s ', 
            'ₜ': ' sub t '
        }
        
        self.superscripts = {
            '⁰': ' to the zero ', '¹': ' to the one ', 
            '²': ' squared ', '³': ' cubed ',
            '⁴': ' to the fourth ', '⁵': ' to the fifth ',
            '⁶': ' to the sixth ', '⁷': ' to the seventh ',
            '⁸': ' to the eighth ', '⁹': ' to the ninth ',
            'ⁿ': ' to the n ', 'ⁱ': ' to the i '
        }
        
        self.axiom_pattern = re.compile(r'\bA(\d{1,3})\b')
        self.law_pattern = re.compile(r'\bL(\d{1,2})\b')
        
        # Load Math Translations
        self.math_translations = self.load_math_translations()

    def remove_code_blocks(self, text: str) -> str:
        """Remove fenced code blocks from text."""
        text = re.sub(r'```[\w]*\n[\s\S]*?```', '', text)
        text = re.sub(r'~~~[\w]*\n[\s\S]*?~~~', '', text)
        return text
    
    def remove_images(self, text: str) -> str:
        """Remove image references from text."""
        text = re.sub(r'!\[\[([^\]]+)\]\]', '', text)
        text = re.sub(r'!\[([^\]]*)\]\([^)]+\)', '', text)
        text = re.sub(r'<img[^>]*>', '', text)
        return text
    
    def remove_inline_code(self, text: str) -> str:
        """Remove inline code markers but keep text."""
        text = re.sub(r'`([^`]+)`', r'\1', text)
        return text

    def remove_hashtags(self, text: str) -> str:
        """Removes hashtags from text."""
        text = re.sub(r'(?:\s+#\w+)+$', '', text, flags=re.MULTILINE)
        text = re.sub(r'#(\w+)', r'\1', text)
        return text
    
    def remove_links(self, text: str) -> str:
        """Remove links from text for TTS."""
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
        text = re.sub(r'\[\[([^\]|]+)\|([^\]]+)\]\]', r'\2', text)
        text = re.sub(r'\[\[([^\]]+)\]\]', r'\1', text)
        text = re.sub(r'https?://[^\s]+', '', text)
        text = re.sub(r'ftp://[^\s]+', '', text)
        text = re.sub(r'www\.[^\s]+', '', text)
        text = re.sub(r'\S+@\S+\.\S+', '', text)
        return text

    def load_math_translations(self) -> Dict[str, str]:
        """Loads the math translation table from the consolidated master Excel file."""
        mapping = {}
        script_dir = os.path.dirname(__file__)
        parent_dir = os.path.dirname(script_dir)  # TTS_Pipeline root
        candidates = [
            'MATH_TRANSLATION_MASTER.xlsx',
            os.path.join(script_dir, 'MATH_TRANSLATION_MASTER.xlsx'),
            os.path.join(parent_dir, 'config', 'MATH_TRANSLATION_MASTER.xlsx'),
            os.path.join(parent_dir, 'MATH_TRANSLATION_MASTER.xlsx')
        ]
        
        file_path = None
        for path in candidates:
            if os.path.exists(path):
                file_path = path
                break
        
        if not file_path:
            print("[WARN] MATH_TRANSLATION_MASTER.xlsx not found. Equations will be skipped.")
            return mapping

        try:
            print(f"[INFO] Loading math translations from: {file_path}")
            df = pd.read_excel(file_path)
            
            latex_col = 'latex'
            audio_col = 'tts_audio'
            
            if latex_col not in df.columns or audio_col not in df.columns:
                print(f"[ERROR] Master file missing required columns: {latex_col}, {audio_col}")
                return mapping
            
            for index, row in df.iterrows():
                latex = str(row[latex_col]).strip()
                audio = str(row[audio_col]).strip()
                latex_norm = re.sub(r'\s+', ' ', latex)
                
                if latex and audio and audio.lower() != 'nan':
                    mapping[latex] = audio
                    mapping[latex_norm] = audio
                    
            print(f"[INFO] Loaded {len(mapping)} math translation pairs from master file.")
            
        except Exception as e:
            print(f"[ERROR] Failed to load math translations: {e}")
            
        return mapping

    def find_equation_translation(self, equation: str) -> str:
        """Find translation with multiple matching strategies."""
        clean_eq = equation.replace('$', '').strip()
        
        if clean_eq in self.math_translations:
            return self.math_translations[clean_eq]
        
        normalized = re.sub(r'\s+', ' ', clean_eq)
        if normalized in self.math_translations:
            return self.math_translations[normalized]
        
        no_spaces = re.sub(r'\s+', '', clean_eq)
        if no_spaces in self.math_translations:
            return self.math_translations[no_spaces]
        
        return self.generate_equation_fallback(clean_eq)

    def generate_equation_fallback(self, equation: str) -> str:
        """Generate intelligent fallback text for unknown equations."""
        eq = equation.lower()
        if '=' in eq:
            if 'delta' in eq or '∂' in eq:
                return "a change or difference equation"
            elif 'int' in eq or '∫' in eq:
                return "an integral equation"
            elif 'sum' in eq or '∑' in eq:
                return "a summation equation"
            else:
                return "an equation"
        else:
            return "a complex mathematical equation"

    def process_latex_blocks(self, text: str) -> str:
        """Process LaTeX blocks."""
        def replace_match(match):
            content = match.group(0)
            inner = match.group(1) if len(match.groups()) > 0 else match.group(0)
            clean_inner = inner.replace('$', '').strip()
            is_display_math = content.startswith('$$') and content.endswith('$$')
            
            if re.match(r'^\s*\$?\d+[\d,\.]*\s*$', clean_inner):
                return content
            
            if len(clean_inner.strip()) <= 1:
                single_char = clean_inner.strip().lower()
                if single_char in self.greek_lower:
                    return f" {self.greek_lower[single_char]} "
                return content
            
            translation = self.find_equation_translation(clean_inner)
            if translation:
                return f" {translation} "
            elif is_display_math:
                return ""
            return content

        text = re.sub(r'\$\$(.*?)\$\$', replace_match, text, flags=re.DOTALL)
        text = re.sub(r'(?<!\$)\$(?!\$)(.*?)(?<!\$)\$', replace_match, text)
        return text

    def detect_markdown_table(self, text: str) -> List[Tuple[int, int, str]]:
        """Detect markdown tables in text."""
        tables = []
        lines = text.split('\n')
        i = 0
        
        while i < len(lines):
            line = lines[i].strip()
            if '|' in line and (line.startswith('|') or line.count('|') >= 2):
                table_start = i
                table_lines = [lines[i]]
                i += 1
                
                while i < len(lines):
                    line = lines[i].strip()
                    if '|' in line and (line.startswith('|') or line.count('|') >= 2):
                        table_lines.append(lines[i])
                        i += 1
                    elif line == '':
                        if i + 1 < len(lines) and '|' in lines[i + 1]:
                            table_lines.append(lines[i])
                            i += 1
                        else:
                            break
                    else:
                        break
                
                if len(table_lines) >= 2:
                    table_text = '\n'.join(table_lines)
                    tables.append((table_start, i, table_text))
            else:
                i += 1
        
        return tables
    
    def parse_markdown_table(self, table_text: str) -> Tuple[List[str], List[List[str]]]:
        """Parse a markdown table into headers and rows."""
        lines = [line.strip() for line in table_text.split('\n') if line.strip()]
        if not lines:
            return [], []
        
        header_line = lines[0]
        headers = [cell.strip() for cell in header_line.split('|') if cell.strip()]
        
        data_start = 1
        if len(lines) > 1 and re.match(r'^[\s\|:\-]+$', lines[1]):
            data_start = 2
        
        data_rows = []
        for line in lines[data_start:]:
            if '|' in line:
                cells = [cell.strip() for cell in line.split('|') if cell.strip()]
                if cells:
                    data_rows.append(cells)
        
        return headers, data_rows
    
    def table_to_narrative(self, table_text: str) -> str:
        """Convert a markdown table to narrative prose."""
        headers, rows = self.parse_markdown_table(table_text)
        if not headers or not rows:
            return ""
        
        narratives = []
        for row in rows:
            if len(row) >= 2:
                variable = row[0]
                values = ', '.join(row[1:])
                narratives.append(f"{variable}: {values}.")
        
        result = []
        for i in range(0, len(narratives), 3):
            chunk = narratives[i:i+3]
            result.append(' '.join(chunk))
        
        return '\n\n'.join(result)
    
    def process_tables(self, text: str) -> str:
        """Convert all markdown tables to narrative prose."""
        tables = self.detect_markdown_table(text)
        if not tables:
            return text
        
        lines = text.split('\n')
        for start_line, end_line, table_text in reversed(tables):
            narrative = self.table_to_narrative(table_text)
            if narrative:
                narrative_lines = ["", "The following data shows:", narrative, ""]
                lines[start_line:end_line] = narrative_lines
        
        return '\n'.join(lines)
    
    def optimize_numbers_for_tts(self, text: str) -> str:
        """Optimize number formatting for TTS."""
        text = re.sub(r'(\d)%', r'\1 percent', text)
        text = re.sub(r'\b(\d+),?000,?000\b', r'\1 million', text)
        text = re.sub(r'\b(\d+),?000\b', r'\1 thousand', text)
        return text

    def extract_tts_blocks(self, text: str) -> Tuple[str, List[str]]:
        tts_pattern = re.compile(r'%%tts\s*(.*?)\s*%%', re.DOTALL | re.IGNORECASE)
        tts_blocks = tts_pattern.findall(text)
        text_with_markers = tts_pattern.sub('<<TTS_BLOCK>>', text)
        return text_with_markers, tts_blocks
    
    def reinsert_tts_blocks(self, text: str, tts_blocks: list) -> str:
        for block in tts_blocks:
            text = text.replace('<<TTS_BLOCK>>', block.strip(), 1)
        text = text.replace('<<TTS_BLOCK>>', '', -1)
        return text
    
    def normalize_greek(self, text: str) -> str:
        for greek, spoken in {**self.greek_lower, **self.greek_upper}.items():
            text = text.replace(greek, f' {spoken} ')
        return text
    
    def normalize_special_letters(self, text: str) -> str:
        for letter, spoken in self.special_letters.items():
            text = text.replace(letter, f' {spoken} ')
        return text
    
    def normalize_symbols(self, text: str) -> str:
        for symbol, spoken in self.theophysics_symbols.items():
            text = text.replace(symbol, f' {spoken} ')
        return text
    
    def normalize_subscripts(self, text: str) -> str:
        for sub, spoken in self.subscripts.items():
            text = text.replace(sub, spoken)
        return text
    
    def normalize_superscripts(self, text: str) -> str:
        for sup, spoken in self.superscripts.items():
            text = text.replace(sup, spoken)
        return text
    
    def normalize_axiom_refs(self, text: str) -> str:
        def replace_axiom(match):
            num = match.group(1)
            return f' Axiom {num} '
        return self.axiom_pattern.sub(replace_axiom, text)
    
    def normalize_law_refs(self, text: str) -> str:
        law_names = {
            '1': 'Law 1, Unity', '2': 'Law 2, Duality', '3': 'Law 3, Trinity',
            '4': 'Law 4, Quaternary Foundation', '5': 'Law 5, Quintessence',
            '6': 'Law 6, Hexadic Harmony', '7': 'Law 7, Septenary Completion',
            '8': 'Law 8, Octave Recursion', '9': 'Law 9, Ennead Fulfillment',
            '10': 'Law 10, Decadic Totality'
        }
        def replace_law(match):
            num = match.group(1)
            return f' {law_names.get(num, f"Law {num}")} '
        return self.law_pattern.sub(replace_law, text)

    def remove_yaml_frontmatter(self, text: str) -> str:
        """Remove YAML frontmatter from the beginning of documents."""
        if text.startswith('---'):
            lines = text.split('\n')
            in_frontmatter = False
            frontmatter_end = -1

            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped == '---':
                    if not in_frontmatter:
                        in_frontmatter = True
                    else:
                        frontmatter_end = i
                        break

            if frontmatter_end > 0:
                text = '\n'.join(lines[frontmatter_end + 1:])

        text = re.sub(r'^[*]{3,}\s*\n(?:.*?\n)*?[*]{3,}\s*\n', '', text, flags=re.MULTILINE)
        text = re.sub(r'^[+]{3,}\s*\n(?:.*?\n)*?[+]{3,}\s*\n', '', text, flags=re.MULTILINE)
        return text.strip()

    def remove_markdown(self, text: str) -> str:
        """Remove markdown formatting but preserve content."""
        text = re.sub(r'^#{1,6}\s*', '', text, flags=re.MULTILINE)
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
        text = re.sub(r'\*([^*]+)\*', r'\1', text)
        text = re.sub(r'__([^_]+)__', r'\1', text)
        text = re.sub(r'_([^_]+)_', r'\1', text)
        text = re.sub(r'`([^`]+)`', r'\1', text)
        text = re.sub(r'```[^`]*```', '', text, flags=re.DOTALL)
        text = re.sub(r'%%(?!tts).*?%%', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
        text = re.sub(r'^\s*[-*+]\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'^>\s*', '', text, flags=re.MULTILINE)
        return text
    
    def clean_whitespace(self, text: str) -> str:
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r' {2,}', ' ', text)
        text = re.sub(r'\s+([.,!?;:])', r'\1', text)
        return text.strip()
    
    def normalize(self, text: str) -> str:
        """Master normalization pipeline for TTS optimization."""
        text = self.remove_yaml_frontmatter(text)
        text_with_markers, tts_blocks = self.extract_tts_blocks(text)
        text_with_markers = self.remove_code_blocks(text_with_markers)
        text_with_markers = self.remove_images(text_with_markers)
        text_with_markers = self.process_tables(text_with_markers)
        text_with_markers = self.process_latex_blocks(text_with_markers)
        text_with_markers = self.remove_links(text_with_markers)
        text_with_markers = self.remove_hashtags(text_with_markers)
        text_with_markers = self.remove_inline_code(text_with_markers)
        text_with_markers = self.remove_markdown(text_with_markers)
        text = self.reinsert_tts_blocks(text_with_markers, tts_blocks)
        text = self.normalize_symbols(text)
        text = self.normalize_greek(text)
        text = self.normalize_special_letters(text)
        text = self.normalize_subscripts(text)
        text = self.normalize_superscripts(text)
        text = self.normalize_axiom_refs(text)
        text = self.normalize_law_refs(text)
        text = self.optimize_numbers_for_tts(text)
        text = self.clean_whitespace(text)
        return text

_normalizer = None

def get_normalizer() -> TheophysicsNormalizer:
    global _normalizer
    if _normalizer is None:
        _normalizer = TheophysicsNormalizer()
    return _normalizer

def normalize_for_tts(text: str) -> str:
    return get_normalizer().normalize(text)

if __name__ == '__main__':
    test_document = '''
# #Theophysics Update
Here is an equation: $\\Delta E_{\\text{required}} = T \\cdot \\Delta S$.
And another: $$ \\chi = \\iiint (G \\cdot M) dt $$
This is #important.
'''
    normalizer = TheophysicsNormalizer()
    print(normalizer.normalize(test_document))
