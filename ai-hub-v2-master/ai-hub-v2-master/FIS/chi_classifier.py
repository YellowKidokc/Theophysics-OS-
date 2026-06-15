"""Chi Factor Classifier — classifies files by their role in the Master Equation.

chi_local = G * M_eff * E_signal * S_eff * T * K * R * Q * F * C

Every file answers: which part of chi does this serve?

This is the PRIMARY classification pass. Domain classification (THEOPHYSICS,
DEVELOPMENT, etc.) is secondary — it tells you WHAT KIND of file it is.
Chi classification tells you WHAT IT'S FOR.
"""

import re
from collections import defaultdict
from pathlib import Path
from typing import Optional

# Root path for the Master Equation File System
MEQS_ROOT = r"C:\Users\lowes\Desktop\Theophysics-OS-clone\Master_Equation_File_System_Starter\THEOPHYSICS"


# ─── CHI FACTOR DEFINITIONS ──────────────────────────────────────────────────
# Each factor has: symbol, name, description, keyword signals, folder target

CHI_FACTORS = {
    'G': {
        'name': 'Grace',
        'law': 'Law 1 (Gravitation) / Law 8 (Relativity)',
        'description': 'Grace externality, gravitational analogy, frame-independent gift',
        'keywords': [
            'grace', 'charis', 'gravitational', 'curvature', 'spacetime',
            'general relativity', 'geodesic', 'metric tensor', 'ricci',
            'christoffel', 'grace operator', 'grace externality', 'gift',
            'unmerited', 'favor', 'frame lock', 'frame independent',
            'equivalence principle', 'free fall', 'tidal force',
        ],
        'folder': '02_LAWS_BY_FACTOR/G_GRAVITY_GRACE',
    },
    'M': {
        'name': 'Moral Alignment (M_eff)',
        'law': 'Law 2 (Motion F=ma)',
        'description': 'Alignment reception, effective moral mass, will-weighted',
        'keywords': [
            'moral', 'alignment', 'reception', 'will', 'free will',
            'repentance', 'conversion', 'force', 'acceleration', 'mass',
            'inertia', 'momentum', 'resistance', 'sin nature', 'flesh',
            'sanctification', 'obedience', 'surrender', 'submission',
            'moral mass', 'm_eff', 'effective mass', 'moral inertia',
        ],
        'folder': '02_LAWS_BY_FACTOR/M_MOTION_ALIGNMENT',
    },
    'E': {
        'name': 'Truth Signal (E_signal)',
        'law': 'Law 3 (Electromagnetism)',
        'description': 'Truth/deception duality, electromagnetic witness, glory, doxa',
        'keywords': [
            'truth', 'deception', 'witness', 'testimony', 'light',
            'electromagnetic', 'maxwell', 'electric field', 'magnetic',
            'glory', 'doxa', 'revelation', 'illumination', 'e_signal',
            'signal', 'noise', 'truth signal', 'logos', 'word',
            'scripture', 'bible', 'gospel truth', 'deceptive',
        ],
        'folder': '02_LAWS_BY_FACTOR/E_TRUTH_SIGNAL',
    },
    'S': {
        'name': 'Entropy (S_eff)',
        'law': 'Law 5 (Thermodynamics)',
        'description': 'Judgment, heat death, entropy as adversary identity, corrected kernel',
        'keywords': [
            'entropy', 'thermodynamic', 'second law', 'heat death',
            'disorder', 'chaos', 'judgment', 'justice', 'mercy',
            'free energy', 'helmholtz', 's_eff', 'corrected entropy',
            'boltzmann', 'temperature', 'heat', 'decay', 'degradation',
            'adversary', 'enemy', 'satan', 'destruction', 'corruption',
        ],
        'folder': '02_LAWS_BY_FACTOR/S_THERMO_JUDGMENT',
    },
    'T': {
        'name': 'Time / Kairos',
        'law': 'Law 8 (Relativity) / General',
        'description': 'Temporal structure, kairos vs chronos, time-translation symmetry',
        'keywords': [
            'time', 'temporal', 'kairos', 'chronos', 'moment',
            'season', 'appointed', 'time translation', 'noether',
            'symmetry', 'conservation', 'eternal', 'everlasting',
            'timeline', 'eschatology', 'prophecy timing', 'age',
        ],
        'folder': '02_LAWS_BY_FACTOR/T_TIME_SEQUENCE',
    },
    'K': {
        'name': 'Knowledge / Information',
        'law': 'Law 6 (Information/Shannon)',
        'description': 'Logos vs chaos, channel capacity, Shannon base layer',
        'keywords': [
            'knowledge', 'information', 'shannon', 'channel capacity',
            'bandwidth', 'logos', 'word', 'communication', 'signal',
            'noise ratio', 'snr', 'bit', 'encoding', 'transmission',
            'sanctification', 'holiness', 'growth', 'wisdom',
            'understanding', 'discernment', 'revelation knowledge',
        ],
        'folder': '02_LAWS_BY_FACTOR/K_LOGOS_INFORMATION',
    },
    'R': {
        'name': 'Relational Coupling',
        'law': 'Law 4 (Strong Force)',
        'description': 'Love/captivity, Yukawa potential, fruits of the spirit',
        'keywords': [
            'love', 'agape', 'relationship', 'coupling', 'bond',
            'strong force', 'yukawa', 'confinement', 'captivity',
            'freedom', 'liberation', 'fruits', 'fruit of the spirit',
            'joy', 'peace', 'patience', 'kindness', 'goodness',
            'faithfulness', 'gentleness', 'self control', 'community',
            'fellowship', 'koinonia', 'relational',
        ],
        'folder': '02_LAWS_BY_FACTOR/R_RELATION_BINDING',
    },
    'Q': {
        'name': 'Quantum / Faith',
        'law': 'Law 7 (Quantum)',
        'description': 'Faith vs doubt/control, measurement problem, observer effect',
        'keywords': [
            'quantum', 'faith', 'doubt', 'uncertainty', 'measurement',
            'observer', 'collapse', 'superposition', 'entanglement',
            'wave function', 'probability', 'heisenberg', 'control',
            'trust', 'belief', 'pistis', 'armor of god', 'shield',
            'helmet', 'sword', 'breastplate',
        ],
        'folder': '02_LAWS_BY_FACTOR/Q_QUANTUM_FAITH',
    },
    'F': {
        'name': 'Moral Force / Conservation',
        'law': 'Law 9 (Weak Force)',
        'description': 'Moral conservation, directional decay, atonement, CP violation',
        'keywords': [
            'moral conservation', 'weak force', 'decay', 'beta decay',
            'parity violation', 'cp violation', 'atonement', 'sacrifice',
            'cross', 'redemption', 'forgiveness', 'sin', 'repentance',
            'irreversible', 'directional', 'one way', 'noether',
            'conservation law', 'moral energy', 'moral force',
        ],
        'folder': '02_LAWS_BY_FACTOR/F_WEAK_SIN_CONSERVATION',
    },
    'C': {
        'name': 'Coherence / Christ',
        'law': 'Law 10 (Coherence)',
        'description': 'C IS chi. Christ as coherence. Decoherence is derivative.',
        'keywords': [
            'coherence', 'decoherence', 'christ', 'christological',
            'colossians', 'holds together', 'unity', 'integrity',
            'wholeness', 'completion', 'kingdom', 'shalom', 'telos',
            'no drift', 'topology', 'chi field', 'master equation',
            'lowe coherence', 'lagrangian', 'convergence',
        ],
        'folder': '02_LAWS_BY_FACTOR/C_COHERENCE_CHRIST',
    },
    'CHI': {
        'name': 'Master Equation (χ)',
        'law': 'All Laws / System Level',
        'description': 'The master equation itself, cross-factor, system-level',
        'keywords': [
            'master equation', 'chi', 'chi field', 'chi local',
            'ten laws', 'all laws', 'unified', 'integration',
            'cross domain', 'isomorphism', 'framework', 'system',
            'principia', 'theophysics', 'complete', 'full model',
        ],
        'folder': '01_CHI_KERNEL/MASTER_EQUATION_KERNEL',
        'sub_folders': {
            'meff': '01_CHI_KERNEL/ALIGNMENT_MEFF',
            'seff': '01_CHI_KERNEL/CORRECTED_ENTROPY_SEFF',
            'nodrift': '01_CHI_KERNEL/NO_DRIFT_TOPOLOGY',
            'kernel': '01_CHI_KERNEL/MASTER_EQUATION_KERNEL',
        },
    },
}

# ─── STATE CODES ──────────────────────────────────────────────────────────────
STATE_CODES = {
    'F': 'Final / Canonical',
    'W': 'Working / Active',
    'D': 'Draft',
    'R': 'Review / Needs verification',
    'X': 'Experimental / Speculative',
    'A': 'Archived / Superseded',
}


def classify_chi_factor(keywords: list, text: str = '', filename: str = '') -> dict:
    """Classify a file by its primary chi factor.
    
    Returns:
        dict with primary_factor, secondary_factors, confidence,
        matched_keywords, suggested_folder, suggested_state
    """
    scores = {}
    matched_by_factor = {}
    
    # Combine all text for matching
    search_text = ' '.join(keywords).lower()
    if text:
        search_text += ' ' + text[:3000].lower()
    if filename:
        search_text += ' ' + filename.lower()
    
    for factor, info in CHI_FACTORS.items():
        score = 0
        matched = []
        
        for kw in info['keywords']:
            kw_lower = kw.lower()
            # Exact match in keywords list
            if kw_lower in [k.lower() for k in keywords]:
                score += 15
                matched.append(kw)
            # Substring in search text
            elif kw_lower in search_text:
                score += 5
                matched.append(f'~{kw}')
        
        if score > 0:
            scores[factor] = score
            matched_by_factor[factor] = matched
    
    if not scores:
        return {
            'primary_factor': None,
            'secondary_factors': [],
            'confidence': 0,
            'matched': [],
            'suggested_folder': '00_INBOX',
            'chi_role': 'unclassified',
        }
    
    # Sort by score
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    primary = ranked[0]
    secondary = [f for f, s in ranked[1:4] if s > 10]
    
    # Confidence: primary score relative to total
    total = sum(scores.values())
    confidence = min(round(primary[1] / max(total, 1) * 100, 1), 99)
    
    factor_info = CHI_FACTORS[primary[0]]
    
    return {
        'primary_factor': primary[0],
        'primary_name': factor_info['name'],
        'primary_law': factor_info['law'],
        'secondary_factors': secondary,
        'confidence': confidence,
        'score': primary[1],
        'matched': matched_by_factor.get(primary[0], []),
        'all_scores': {f: s for f, s in ranked[:5]},
        'suggested_folder': factor_info['folder'],
        'chi_role': factor_info['description'],
        'vector': build_chi_vector(scores),
    }


def build_chi_vector(scores: dict) -> str:
    """Build the chi vector string: G0M0E0S0T0K0R0Q0F0C0
    
    Each position is 0 (no signal) or 1 (signal present).
    """
    factors = ['G', 'M', 'E', 'S', 'T', 'K', 'R', 'Q', 'F', 'C']
    vector = ''
    for f in factors:
        val = 1 if scores.get(f, 0) > 10 else 0
        vector += f'{f}{val}'
    return vector


def generate_meqs_filename(file_info: dict, chi_result: dict, 
                           state: str = 'W') -> str:
    """Generate Master Equation File System filename.
    
    Pattern: PRIMARYVAR__ENTITY__STATE__DATE__SHORTCODE.ext
    """
    primary = chi_result.get('primary_factor', 'UC')
    
    # Entity: from keywords or filename
    keywords = file_info.get('keywords', [])
    if keywords:
        entity = '_'.join(k.upper().replace(' ', '_') for k in keywords[:3])
    else:
        entity = Path(file_info.get('filename', 'UNNAMED')).stem.upper()
        entity = re.sub(r'[^A-Z0-9_]', '_', entity)[:40]
    
    # Date
    from datetime import datetime
    date = datetime.now().strftime('%Y%m%d')
    
    # Shortcode: first letters of keywords
    if keywords:
        shortcode = ''.join(k[0].upper() for k in keywords[:4] if k)
    else:
        shortcode = primary
    
    ext = file_info.get('ext', '.md').lstrip('.')
    
    return f"{primary}__{entity}__{state}__{date}__{shortcode}.{ext}"


def generate_frontmatter(file_info: dict, chi_result: dict,
                         state: str = 'W') -> str:
    """Generate YAML frontmatter for a classified file."""
    primary = chi_result.get('primary_factor', 'UC')
    secondary = chi_result.get('secondary_factors', [])
    vector = chi_result.get('vector', 'G0M0E0S0T0K0R0Q0F0C0')
    
    keywords = file_info.get('keywords', [])
    entity = '_'.join(k.upper() for k in keywords[:3]) if keywords else 'UNNAMED'
    
    from datetime import datetime
    today = datetime.now().strftime('%Y-%m-%d')
    
    frontmatter = f"""---
entity: {entity}
primary_chi_factor: {primary}
secondary_chi_factors: [{', '.join(secondary)}]
state: {state}
audience: AI_RESEARCH
risk: R1
chi_role: "{chi_result.get('chi_role', '')}"
kernel_relation: "{chi_result.get('primary_name', '')} — {chi_result.get('primary_law', '')}"
vector: {vector}
hash: ""
address: ""
status: {'working' if state == 'W' else 'final' if state == 'F' else 'draft'}
last_reviewed: {today}
---"""
    return frontmatter


def batch_classify_chi(files: list) -> list:
    """Classify a batch of files by chi factor.
    
    Takes output from auto_sort.classify_directory().
    Returns enriched list with chi classification added.
    """
    results = []
    for f in files:
        keywords = [k['keyword'] for k in f.get('keywords', [])]
        text = f.get('text_preview', '')
        filename = f.get('filename', '')
        
        chi = classify_chi_factor(keywords, text, filename)
        
        f['chi_classification'] = chi
        f['meqs_filename'] = generate_meqs_filename(f, chi)
        f['meqs_folder'] = chi.get('suggested_folder', '00_INBOX')
        
        results.append(f)
    
    return results


def print_chi_classification(files: list):
    """Pretty-print chi factor classification results."""
    # Group by primary factor
    by_factor = defaultdict(list)
    for f in files:
        chi = f.get('chi_classification', {})
        factor = chi.get('primary_factor') or 'NONE'
        by_factor[factor].append(f)
    
    print(f"\n{'='*65}")
    print(f"  MASTER EQUATION CLASSIFICATION — {len(files)} files")
    print(f"  chi_local = G · M · E · S · T · K · R · Q · F · C")
    print(f"{'='*65}")
    
    for factor in ['CHI', 'G', 'M', 'E', 'S', 'T', 'K', 'R', 'Q', 'F', 'C', 'NONE']:
        if factor not in by_factor:
            continue
        flist = by_factor[factor]
        info = CHI_FACTORS.get(factor, {})
        name = info.get('name', 'Unclassified')
        
        print(f"\n  [{factor}] {name} — {len(flist)} files")
        if info.get('law'):
            print(f"      {info['law']}")
        
        for f in flist[:6]:
            chi = f.get('chi_classification', {})
            conf = chi.get('confidence', 0)
            vec = chi.get('vector', '')
            meqs = f.get('meqs_filename', '')
            print(f"    {conf:3.0f}%  {f['filename'][:35]:<35s}  → {meqs[:40]}")
            if chi.get('secondary_factors'):
                print(f"         secondary: {', '.join(chi['secondary_factors'])}  vector: {vec}")
        if len(flist) > 6:
            print(f"    ... +{len(flist) - 6} more")
    
    # Summary vector
    factor_counts = {f: len(by_factor.get(f, [])) for f in ['G','M','E','S','T','K','R','Q','F','C','CHI']}
    active = [f"{k}:{v}" for k, v in factor_counts.items() if v > 0]
    print(f"\n  Factor distribution: {' · '.join(active)}")
    if 'NONE' in by_factor:
        print(f"  Unclassified: {len(by_factor['NONE'])} files → 00_INBOX")
    print(f"{'='*65}\n")
