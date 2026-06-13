"""
Fix Math Translation Master + Add H10 Equations
================================================
Uses OpenAI GPT-3.5 to regenerate the 303 bad translations
and add the new Sin-Impedance equations from H10.

Cost estimate: ~$1-2 total (one-time)

Author: David Lowe / Theophysics Project
"""

import os
import pandas as pd
from openai import OpenAI
from pathlib import Path
import time
import json

# Configuration
MASTER_FILE = r"O:\Theophysics_Backend\TTS_Engines\TTS_Pipeline\config\MATH_TRANSLATION_MASTER.xlsx"
OUTPUT_FILE = r"O:\Theophysics_Backend\TTS_Engines\TTS_Pipeline\config\MATH_TRANSLATION_MASTER_FIXED.xlsx"
CACHE_FILE = r"O:\Theophysics_Backend\TTS_Engines\TTS_Pipeline\config\translation_cache.json"

# New H10 Sin-Impedance equations to add
H10_EQUATIONS = [
    {
        'latex': r'$\Phi_{eff} = \Phi_{max} \cdot e^{-\alpha S}$',
        'paper_ref': 'H10',
        'conceptual_meaning': 'Effective consciousness equals potential consciousness times sin impedance factor'
    },
    {
        'latex': r'$G_s = e^{-\alpha S}$',
        'paper_ref': 'H10',
        'conceptual_meaning': 'Spiritual conductance decays exponentially with accumulated sin'
    },
    {
        'latex': r'$G_s(t) = e^{-\alpha \cdot S(t)}$',
        'paper_ref': 'H10',
        'conceptual_meaning': 'Spiritual conductance as function of time and accumulated sin'
    },
    {
        'latex': r'$\Phi_{eff}(t) = \Phi_{max} \cdot G_s(t)$',
        'paper_ref': 'H10',
        'conceptual_meaning': 'Effective consciousness is potential times spiritual conductance'
    },
    {
        'latex': r'$\frac{dS}{dt} = +\lambda$',
        'paper_ref': 'H10',
        'conceptual_meaning': 'Sin accumulates naturally at rate lambda without grace'
    },
    {
        'latex': r'$\frac{dS}{dt} = -\mu \cdot G_{grace} + \lambda_{residual}$',
        'paper_ref': 'H10',
        'conceptual_meaning': 'With grace, sin decreases by grace effectiveness minus residual sin rate'
    },
    {
        'latex': r'$\frac{dG_s}{dt} = -\alpha G_s \cdot \frac{dS}{dt}$',
        'paper_ref': 'H10',
        'conceptual_meaning': 'Conductance change rate depends on current conductance and sin change'
    },
    {
        'latex': r'$\frac{d\Phi_{eff}}{dt} < 0$',
        'paper_ref': 'H10',
        'conceptual_meaning': 'Without grace, consciousness quality continuously degrades'
    },
    {
        'latex': r'$\frac{d\Phi_{eff}}{dt} > 0$',
        'paper_ref': 'H10',
        'conceptual_meaning': 'With sufficient grace, consciousness quality improves over time'
    },
    {
        'latex': r'$S(t^+) = S(t^-) - \Delta S_{confessed}$',
        'paper_ref': 'H10',
        'conceptual_meaning': 'Repentance produces discontinuous drop in accumulated sin'
    },
    {
        'latex': r'$\Phi_{moral}(t) = \Phi_{moral}(0) \cdot e^{-\beta \cdot \int sin_{moral} \, dt}$',
        'paper_ref': 'H10',
        'conceptual_meaning': 'Moral consciousness degrades faster than general consciousness from moral sin'
    },
    {
        'latex': r'$I_{HS} = V_{grace} \cdot G_0 \cdot e^{-\alpha \cdot S}$',
        'paper_ref': 'H10',
        'conceptual_meaning': 'Holy Spirit flow equals grace voltage times base conductance times sin impedance'
    },
]


def load_cache():
    """Load translation cache."""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_cache(cache):
    """Save translation cache."""
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, indent=2)


def translate_equation(client, latex: str, conceptual: str = "", cache: dict = None) -> str:
    """
    Translate a LaTeX equation to spoken TTS form using OpenAI.
    """
    # Check cache first
    cache_key = latex.strip()
    if cache and cache_key in cache:
        print(f"  [CACHE HIT]")
        return cache[cache_key]
    
    prompt = f"""Translate this mathematical equation for text-to-speech audio.
Provide a natural spoken translation optimized for listening - something a narrator would say.

Guidelines:
- Start with what the equation represents conceptually
- Then describe the mathematical relationship in plain English
- Keep it under 60 words
- No LaTeX, no symbols - just speakable words
- Sound natural, like explaining to an interested friend

LaTeX equation: {latex}
{f"Context: {conceptual}" if conceptual else ""}

Provide ONLY the spoken translation, nothing else."""

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a math translator for audio narration. Convert equations to natural spoken English."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=150
        )
        
        translation = response.choices[0].message.content.strip()
        
        # Cache result
        if cache is not None:
            cache[cache_key] = translation
            save_cache(cache)
        
        return translation
        
    except Exception as e:
        print(f"  [ERROR] {e}")
        return f"A mathematical equation from the Theophysics framework."


def is_bad_translation(audio: str) -> bool:
    """Check if a translation needs fixing."""
    if not audio or audio == 'nan':
        return True
    if audio.startswith("When we read this"):
        return True
    if audio.startswith("$"):  # Raw LaTeX leaked through
        return True
    if len(audio) < 20:  # Too short to be useful
        return True
    return False


def main():
    # Check for API key
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("="*60)
        print("OPENAI_API_KEY not found in environment!")
        print("Set it with: set OPENAI_API_KEY=your-key-here")
        print("="*60)
        return
    
    client = OpenAI(api_key=api_key)
    cache = load_cache()
    
    print("="*60)
    print("MATH TRANSLATION FIXER + H10 ADDER")
    print("="*60)
    
    # Load master file
    print(f"\nLoading: {MASTER_FILE}")
    df = pd.read_excel(MASTER_FILE)
    print(f"Total rows: {len(df)}")
    
    # Count bad translations
    bad_indices = []
    for i, row in df.iterrows():
        audio = str(row.get('tts_audio', ''))
        if is_bad_translation(audio):
            bad_indices.append(i)
    
    print(f"Bad translations to fix: {len(bad_indices)}")
    print(f"New H10 equations to add: {len(H10_EQUATIONS)}")
    
    # Cost estimate
    total_to_translate = len(bad_indices) + len(H10_EQUATIONS)
    cost_estimate = total_to_translate * 0.003
    print(f"\nEstimated cost: ${cost_estimate:.2f}")
    
    confirm = input("\nProceed? (yes/no): ").strip().lower()
    if confirm not in ['yes', 'y']:
        print("Aborted.")
        return
    
    # Fix bad translations
    print("\n" + "="*60)
    print("FIXING BAD TRANSLATIONS")
    print("="*60)
    
    fixed_count = 0
    for idx in bad_indices:
        row = df.loc[idx]
        latex = str(row.get('latex', ''))
        conceptual = str(row.get('conceptual_meaning', ''))
        
        print(f"\n[{fixed_count+1}/{len(bad_indices)}] {latex[:50]}...")
        
        new_audio = translate_equation(client, latex, conceptual, cache)
        df.at[idx, 'tts_audio'] = new_audio
        
        print(f"  => {new_audio[:60]}...")
        fixed_count += 1
        
        # Rate limiting
        time.sleep(0.1)
    
    print(f"\nFixed {fixed_count} translations.")
    
    # Add H10 equations
    print("\n" + "="*60)
    print("ADDING H10 SIN-IMPEDANCE EQUATIONS")
    print("="*60)
    
    # Find max ID
    max_id = df['id'].max() if 'id' in df.columns else len(df)
    
    for i, eq in enumerate(H10_EQUATIONS):
        print(f"\n[{i+1}/{len(H10_EQUATIONS)}] {eq['latex'][:50]}...")
        
        audio = translate_equation(client, eq['latex'], eq['conceptual_meaning'], cache)
        
        new_row = {
            'id': max_id + i + 1,
            'latex': eq['latex'],
            'tts_audio': audio,
            'short_form': '',
            'medium_form': '',
            'conceptual_meaning': eq['conceptual_meaning'],
            'paper_ref': eq['paper_ref'],
            'source_file': 'H10_Consciousness_Moral_Coherence.md'
        }
        
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        print(f"  => {audio[:60]}...")
        
        time.sleep(0.1)
    
    # Save
    print("\n" + "="*60)
    print(f"SAVING TO: {OUTPUT_FILE}")
    print("="*60)
    
    df.to_excel(OUTPUT_FILE, index=False)
    print(f"Saved {len(df)} rows.")
    
    # Also save a backup of the cache
    print(f"Cache saved to: {CACHE_FILE}")
    print(f"Cache size: {len(cache)} translations")
    
    print("\n" + "="*60)
    print("DONE!")
    print("="*60)
    print(f"\nTo use the fixed file, rename it to MATH_TRANSLATION_MASTER.xlsx")
    print(f"Or update the path in theophysics_normalizer.py")


if __name__ == '__main__':
    main()
