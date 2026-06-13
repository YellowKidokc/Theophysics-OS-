"""
Extract equations from 00_MATH_SUMMARY.md and update master file
"""
import re
import pandas as pd
# No OrderedDict needed - using set() instead

def extract_equations_from_file(filepath):
    """Extract all unique equations from markdown file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find all $$ blocks
    display_math = re.findall(r'\$\$(.*?)\$\$', content, re.DOTALL)
    
    # Find all $ inline math (but not $$)
    inline_math = re.findall(r'(?<!\$)\$(?!\$)(.*?)(?<!\$)\$(?!\$)', content)
    
    # Clean and deduplicate
    equations = set()
    
    for eq in display_math:
        clean = eq.strip()
        if clean and len(clean) > 2:  # Skip very short ones
            equations.add(clean)
    
    for eq in inline_math:
        clean = eq.strip()
        if clean and len(clean) > 3:  # Skip very short ones
            equations.add(clean)
    
    return sorted(equations)

def load_master_file():
    """Load existing master file."""
    try:
        df = pd.read_excel('MATH_TRANSLATION_MASTER.xlsx')
        existing = set(df['latex'].str.strip())
        return df, existing
    except Exception as e:
        print(f"Error loading master file: {e}")
        return None, set()

def generate_translation(equation):
    """Generate a translation for an equation based on patterns."""
    eq = equation.lower()
    
    # Pattern matching for common structures
    if 'frac{d' in eq and '}{dt}' in eq:
        var = re.search(r'\\frac\{d(.+?)\}', equation)
        if var:
            return f"The rate of change of {var.group(1)} with respect to time"
    
    if 'hat{g}' in eq or '\\hat{g}' in eq:
        return "The Grace operator. The external force that changes sign. What the system is open to."
    
    if 'chi' in eq and 'field' in eq:
        return "The chi field. The coherence field that measures integrated information."
    
    if 'alpha' in eq and 'beta' in eq:
        return "The internal will to organize (alpha) versus the drag of entropy (beta). The fight between order and chaos."
    
    if 'lambda' in eq or 'integral' in eq:
        return "An integral functional. A measure of total system behavior over space and time."
    
    if '=' in eq:
        return "An equation describing a relationship or constraint in the system."
    
    return "A mathematical expression from the Theophysics framework."

# Run the extraction
print("="*60)
print("EXTRACTING EQUATIONS FROM 00_MATH_SUMMARY.md")
print("="*60)

filepath = r"O:\_THEO\THEO\TM SUBSTACK\TM SUBSTACK\02_DRAFTING\_Archive\00_MATH_SUMMARY.md"
equations = extract_equations_from_file(filepath)

print(f"\nFound {len(equations)} unique equations")

# Load master file
df_master, existing_equations = load_master_file()

# Find missing ones
missing = []
for eq in equations:
    if eq not in existing_equations:
        missing.append(eq)

print(f"Missing from master file: {len(missing)}")

if missing:
    print("\n" + "="*60)
    print("SAMPLE OF MISSING EQUATIONS:")
    print("="*60)
    for i, eq in enumerate(missing[:10], 1):
        print(f"\n{i}. {eq[:100]}{'...' if len(eq) > 100 else ''}")

print("\n" + "="*60)
print(f"Total to add: {len(missing)} equations")
print("="*60)
