"""
Text Normalization ONLY (No TTS)
==================================
Runs the TTS pipeline normalization WITHOUT audio generation.

Usage:
    python normalize_only.py <input_file> <output_file>
"""

import os
import sys
import re

# Add converters to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import text normalizers
from theophysics_normalizer import normalize_for_tts as normalize_theophysics

# Try to import the standard converters
try:
    from Cardinal import Cardinal
    from Ordinal import Ordinal
    from Decimal import Decimal
    from Fraction import Fraction
    from Measure import Measure
    from Money import Money
    from Date import Date
    from Time import Time
    from Telephone import Telephone
    from Electronic import Electronic
    CONVERTERS_AVAILABLE = True
except ImportError as e:
    print(f"[WARNING] Standard converters not fully available: {e}")
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
        
        # Money
        def replace_money(match):
            try:
                return ' ' + self.money.convert(match.group(0)) + ' '
            except:
                return match.group(0)
        text = self.patterns['money'].sub(replace_money, text)
        
        # Measures
        def replace_measure(match):
            try:
                return ' ' + self.measure.convert(match.group(0)) + ' '
            except:
                return match.group(0)
        text = self.patterns['measure'].sub(replace_measure, text)
        
        # Fractions
        def replace_fraction(match):
            try:
                return ' ' + self.fraction.convert(match.group(0)) + ' '
            except:
                return match.group(0)
        text = self.patterns['fraction'].sub(replace_fraction, text)
        
        # Ordinals
        def replace_ordinal(match):
            try:
                return ' ' + self.ordinal.convert(match.group(0)) + ' '
            except:
                return match.group(0)
        text = self.patterns['ordinal'].sub(replace_ordinal, text)
        
        # Decimals
        def replace_decimal(match):
            try:
                return ' ' + self.decimal.convert(match.group(0)) + ' '
            except:
                return match.group(0)
        text = self.patterns['decimal'].sub(replace_decimal, text)
        
        # Cardinals (last - catches remaining numbers)
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


def main():
    if len(sys.argv) < 3:
        print("Usage: python normalize_only.py <input_file> <output_file>")
        sys.exit(1)
    
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    
    # Validate input
    if not os.path.exists(input_path):
        print(f"[ERROR] Input file not found: {input_path}")
        sys.exit(1)
    
    print(f"[NORMALIZE] Processing: {input_path}")
    
    # Read input
    print("  [1/3] Reading input...")
    with open(input_path, 'r', encoding='utf-8') as f:
        text = f.read()
    print(f"       Input length: {len(text)} characters")
    
    # Normalize
    print("  [2/3] Normalizing text...")
    normalizer = TextNormalizer()
    normalized = normalizer.normalize(text)
    print(f"       Normalized length: {len(normalized)} characters")
    
    # Save output
    print("  [3/3] Saving output...")
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(normalized)
    
    print(f"[SUCCESS] Output saved: {output_path}")


if __name__ == '__main__':
    main()
