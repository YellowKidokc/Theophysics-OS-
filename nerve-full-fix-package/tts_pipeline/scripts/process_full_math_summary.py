"""
Process Full 00_MATH_SUMMARY.md with Enhanced Formatting
=========================================================
Apply the 4-layer translation to ALL equations in the document.

Cost: ~$0.05 for full document with AI (or $0 without)
Result: Publication-ready formatted equations

Author: David Lowe / Theophysics Project
"""

import sys
import time
sys.stdout.reconfigure(encoding='utf-8')

from equation_formatter import EquationFormatter
from pathlib import Path
import re

def count_equations(content: str) -> int:
    """Count substantial equations in document."""
    pattern = r'\$\$(.*?)\$\$'
    matches = re.findall(pattern, content, re.DOTALL)
    
    substantial = 0
    for eq in matches:
        eq_clean = eq.strip()
        if len(eq_clean) > 10 and not eq_clean.replace('.', '').isdigit():
            substantial += 1
    
    return substantial

def main():
    """Process the full document."""
    print("="*70)
    print("PROCESSING FULL 00_MATH_SUMMARY.md")
    print("="*70)
    print()
    
    # Paths
    input_file = r"O:\_THEO\THEO\TM SUBSTACK\TM SUBSTACK\02_DRAFTING\_Archive\00_MATH_SUMMARY.md"
    output_file = r"O:\_THEO\THEO\TM SUBSTACK\TM SUBSTACK\02_DRAFTING\_Archive\00_MATH_SUMMARY_FORMATTED.md"
    
    print(f"Input:  {Path(input_file).name}")
    print(f"Output: {Path(output_file).name}")
    print()
    
    # Read content
    print("Reading document...")
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    lines = content.count('\n')
    eq_count = count_equations(content)
    
    print(f"✓ {lines} lines")
    print(f"✓ ~{eq_count} substantial equations")
    print()
    
    # Cost estimate
    cost_with_ai = eq_count * 0.0004  # Rough estimate
    print("="*70)
    print("COST ESTIMATE")
    print("="*70)
    print(f"Built-in:  $0.00 (FREE)")
    print(f"With AI:   ${cost_with_ai:.2f} (~$0.0004 per equation)")
    print()
    
    # For now, use built-in (AI integration coming next)
    use_ai = False
    print("Using: Built-in translations (FREE)")
    print()
    
    # Create formatter
    print("="*70)
    print("PROCESSING")
    print("="*70)
    print()
    
    formatter = EquationFormatter()
    
    print("Formatting all equations...")
    print("(This may take a minute...)")
    print()
    
    start_time = time.time()
    
    # Process document
    result = formatter.process_document(content, use_ai=use_ai)
    
    elapsed = time.time() - start_time
    
    print(f"✓ Processed in {elapsed:.1f} seconds")
    print()
    
    # Save
    print("Saving formatted document...")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(result)
    
    print(f"✓ Saved to: {output_file}")
    print()
    
    # Summary
    print("="*70)
    print("COMPLETE!")
    print("="*70)
    print()
    print(f"✓ Processed {eq_count} equations")
    print(f"✓ Total cost: $0.00 (built-in)")
    print(f"✓ Output: {Path(output_file).name}")
    print()
    print("="*70)
    print("WHAT YOU NOW HAVE")
    print("="*70)
    print()
    print("Every equation in 00_MATH_SUMMARY.md now has:")
    print()
    print("  1. Callout box (centered)")
    print("  2. Symbol-to-word translation")
    print("  3. Component breakdown")
    print("  4. Plain-talk synthesis")
    print("  5. The real picture (metaphor/gravity)")
    print()
    print("Balance:")
    print("  ✓ NO academic jargon")
    print("  ✓ Plain talk that captures GRAVITY")
    print("  ✓ Respects reader intelligence")
    print("  ✓ Climbs them UP")
    print()
    print("="*70)
    print()
    print("Review the output file and let me know if the balance is good!")
    print()

if __name__ == '__main__':
    main()
