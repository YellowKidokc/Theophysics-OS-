"""
Process 00_MATH_SUMMARY.md - Extract equations, update master, and translate
"""
import re
import pandas as pd
import sys
from pathlib import Path

# Force UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

def extract_equations(filepath):
    """Extract all unique equations."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find all $$ blocks
    display_math = re.findall(r'\$\$(.*?)\$\$', content, re.DOTALL)
    
    equations = set()
    for eq in display_math:
        clean = eq.strip()
        if clean and len(clean) > 2:
            equations.add(clean)
    
    return sorted(equations)

def smart_translation(equation):
    """Generate intelligent translations based on your style."""
    eq = equation.lower()
    
    # Evolution Equation components
    if 'frac{d\\phi}{dt}' in eq or 'frac{dphi}{dt}' in eq:
        return "How fast is coherence changing? The rate things hold together or fall apart."
    
    if 'alpha' in eq and 'mathcal{i}' in eq:
        return "The internal will to organize. The force inside the system that creates order."
    
    if 'beta' in eq and 's(' in eq:
        return "The drag, the decay. Entropy tearing everything apart."
    
    if 'hat{g}(t)' in eq or '\\hat{g}' in eq:
        return "The exogenous operator. The part that shouldn't be there but is. What the system is open to."
    
    # Common physics patterns
    if 'g_{\\mu\\nu}' in eq and 't_{\\mu\\nu}' in eq:
        return "Einstein's field equations with an additional term. Gravity shaped by matter, energy, and the chi field."
    
    if 'frac{d' in eq and '}{dt}' in eq:
        var_match = re.search(r'frac\{d(.+?)\}', equation)
        var_name = var_match.group(1) if var_match else "a variable"
        return f"The rate of change of {var_name} over time. How fast this quantity is evolving."
    
    if '\\chi' in eq or 'chi' in eq:
        if 'field' in eq or 'coherence' in eq:
            return "The chi field. The coherence field measuring integrated information and system organization."
        else:
            return "Chi. The coherence variable that tracks how organized the system is."
    
    if 'psi' in eq and 'rangle' in eq:
        return "A quantum state. A superposition of possibilities waiting to collapse into one actuality."
    
    if 'int' in eq or 'sum' in eq:
        return "An integral or sum. Accumulating contributions over space, time, or states."
    
    if 'langle' in eq and 'rangle' in eq:
        return "An expectation value or inner product. The average or overlap between quantum states."
    
    if '\\boxed' in eq:
        # This is a key result
        return "A key result from the framework. This equation captures a central prediction or constraint."
    
    if '=' in eq and len(eq) < 50:
        return "A defining equation. This sets up a relationship or constraint in the system."
    
    # Fallback
    return "An equation from the Theophysics framework describing constraints on reality."

# Load master file
print("Loading master file...")
df = pd.read_excel('MATH_TRANSLATION_MASTER.xlsx')
existing_latex = set(df['latex'].str.strip())
next_id = df['id'].max() + 1

print(f"Current master file: {len(df)} equations")

# Extract equations
filepath = r"O:\_THEO\THEO\TM SUBSTACK\TM SUBSTACK\02_DRAFTING\_Archive\00_MATH_SUMMARY.md"
print(f"\nExtracting from: {Path(filepath).name}")

equations = extract_equations(filepath)
print(f"Found: {len(equations)} unique equations")

# Find missing
missing = [eq for eq in equations if eq not in existing_latex]
print(f"Missing: {len(missing)} new equations")

if missing:
    print("\nGenerating translations for new equations...")
    new_rows = []
    
    for i, eq in enumerate(missing, 1):
        translation = smart_translation(eq)
        new_row = {
            'id': next_id + i - 1,
            'latex': eq,
            'tts_audio': translation,
            'short_form': '',
            'medium_form': '',
            'conceptual_meaning': '',
            'paper_ref': '00_MATH_SUMMARY',
            'source_file': 'Extracted from 00_MATH_SUMMARY.md'
        }
        new_rows.append(new_row)
        
        if i <= 5:  # Show first 5
            print(f"\n[{i}] {eq[:60]}...")
            print(f"    → {translation[:80]}...")
    
    # Append to master
    df_new = pd.DataFrame(new_rows)
    df_updated = pd.concat([df, df_new], ignore_index=True)
    
    # Save
    print(f"\nSaving updated master file...")
    df_updated.to_excel('MATH_TRANSLATION_MASTER.xlsx', index=False)
    print(f"✓ Added {len(missing)} equations")
    print(f"✓ Total now: {len(df_updated)} equations")

else:
    print("\n✓ All equations already in master file!")

print("\n" + "="*60)
print("READY TO PROCESS FILE")
print("="*60)
print("Master file updated. Now run:")
print("  python math_translation_manager.py")
print("Or:")
print("  python -c \"from theophysics_normalizer import TheophysicsNormalizer; n = TheophysicsNormalizer(); ...\"")
