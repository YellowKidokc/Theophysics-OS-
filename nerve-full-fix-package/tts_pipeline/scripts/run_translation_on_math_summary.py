"""
Run the full translation layer on 00_MATH_SUMMARY.md
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from theophysics_normalizer import TheophysicsNormalizer
from pathlib import Path

# Read the file
input_file = r"O:\_THEO\THEO\TM SUBSTACK\TM SUBSTACK\02_DRAFTING\_Archive\00_MATH_SUMMARY.md"
output_file = r"O:\_THEO\THEO\TM SUBSTACK\TM SUBSTACK\02_DRAFTING\_Archive\00_MATH_SUMMARY_TTS_READY.md"

print("="*60)
print("MATH TRANSLATION LAYER - FULL PROCESSING")
print("="*60)
print(f"Input:  {Path(input_file).name}")
print(f"Output: {Path(output_file).name}")
print("="*60)

# Load normalizer
print("\n[1/3] Loading translation layer...")
normalizer = TheophysicsNormalizer()
print(f"      → Loaded {len(normalizer.math_translations)} translations")

# Read input
print("\n[2/3] Reading input file...")
with open(input_file, 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.count('\n')
equations = content.count('$$')
print(f"      → {lines} lines")
print(f"      → ~{equations} equations")

# Process
print("\n[3/3] Applying translation layer...")
print("      → Math equations → Spoken form")
print("      → Tables → Narrative")
print("      → Links → Removed")
print("      → Numbers → Optimized")

result = normalizer.normalize(content)

# Save
with open(output_file, 'w', encoding='utf-8') as f:
    f.write(result)

print("\n" + "="*60)
print("COMPLETE!")
print("="*60)
print(f"✓ Processed {lines} lines")
print(f"✓ Translated {len([m for m in normalizer.math_translations.items()])} equations")
print(f"✓ Saved to: {output_file}")
print("\n" + "="*60)
print("SAMPLE OUTPUT (first 50 lines):")
print("="*60)
print(result.split('\n', 50)[0] if '\n' in result else result[:2000])
print("\n... (see full output in TTS_READY file)")
