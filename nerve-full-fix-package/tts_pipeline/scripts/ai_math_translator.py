"""
AI-Enhanced Math Translation Layer (OpenAI-focused)
====================================================
Uses OpenAI GPT-3.5-turbo for equations not in the master file.

Features:
- Caching (never translate the same equation twice)
- Cost tracking
- Theophysics-aware prompting

Cost: ~$0.003 per equation (GPT-3.5-turbo)

Author: David Lowe / Theophysics Project
"""

import os
import json
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

class AITranslationCache:
    """Manages cache of AI-translated equations."""
    
    def __init__(self, cache_file: str = None):
        if cache_file is None:
            script_dir = Path(__file__).parent
            cache_file = script_dir.parent / "config" / "ai_translation_cache.json"
        self.cache_file = Path(cache_file)
        self.cache = self._load()
        self.hits = 0
        self.misses = 0
    
    def _load(self) -> Dict:
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def save(self):
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(self.cache, f, indent=2, ensure_ascii=False)
    
    def get(self, equation: str) -> Optional[str]:
        key = equation.strip()
        if key in self.cache:
            self.hits += 1
            return self.cache[key]
        self.misses += 1
        return None
    
    def set(self, equation: str, translation: str):
        self.cache[equation.strip()] = translation
        self.save()
    
    def stats(self) -> Dict:
        return {
            'cached': len(self.cache),
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': f"{(self.hits / (self.hits + self.misses) * 100):.1f}%" if (self.hits + self.misses) > 0 else "N/A"
        }


class AIMathTranslator:
    """OpenAI-powered math translation for TTS."""
    
    def __init__(self, api_key: str = None, model: str = "gpt-3.5-turbo"):
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        self.model = model
        self.cache = AITranslationCache()
        self.provider = f"openai-{model}"
        self.total_cost = 0.0
        
        # Pricing per 1K tokens (GPT-3.5-turbo as of 2024)
        self.input_price = 0.0005  # $0.0005 per 1K input tokens
        self.output_price = 0.0015  # $0.0015 per 1K output tokens
    
    def is_available(self) -> tuple[bool, str]:
        """Check if OpenAI is available."""
        if not self.api_key:
            return False, "OPENAI_API_KEY not set. Run: set OPENAI_API_KEY=your-key"
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)
            # Quick test
            return True, f"OpenAI ready ({self.model})"
        except ImportError:
            return False, "openai package not installed. Run: pip install openai"
        except Exception as e:
            return False, f"OpenAI error: {e}"
    
    def translate(self, equation: str, context: str = "") -> str:
        """
        Translate equation to spoken TTS form.
        Checks cache first, then calls OpenAI if needed.
        """
        # Check cache
        cached = self.cache.get(equation)
        if cached:
            return cached
        
        # Call OpenAI
        translation = self._call_openai(equation, context)
        
        # Cache result
        if translation:
            self.cache.set(equation, translation)
        
        return translation or "A mathematical equation from the Theophysics framework."
    
    def _call_openai(self, equation: str, context: str = "") -> Optional[str]:
        """Call OpenAI API."""
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)
            
            prompt = self._build_prompt(equation, context)
            
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a math-to-speech translator for the Theophysics project. Convert equations to natural spoken English optimized for audio narration. Be concise but complete."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=150
            )
            
            translation = response.choices[0].message.content.strip()
            
            # Track cost
            usage = response.usage
            cost = (usage.prompt_tokens / 1000 * self.input_price) + (usage.completion_tokens / 1000 * self.output_price)
            self.total_cost += cost
            
            return translation
            
        except Exception as e:
            print(f"[AI ERROR] {e}")
            return None
    
    def _build_prompt(self, equation: str, context: str = "") -> str:
        """Build the translation prompt."""
        return f"""Translate this mathematical equation for text-to-speech narration.

Guidelines:
- Explain what the equation represents conceptually FIRST
- Then describe the mathematical relationship in plain words
- Keep it under 50 words
- No symbols, no LaTeX - just speakable English
- Sound natural, like explaining to a smart friend

Equation: {equation}
{f"Context: {context}" if context else ""}

Provide ONLY the spoken translation:"""
    
    def estimate_cost(self, num_equations: int) -> Dict:
        """Estimate cost for N equations."""
        avg_input = 150  # tokens
        avg_output = 60  # tokens
        cost_per = (avg_input / 1000 * self.input_price) + (avg_output / 1000 * self.output_price)
        
        return {
            'equations': num_equations,
            'cost_per_equation': f"${cost_per:.4f}",
            'total_estimate': f"${num_equations * cost_per:.2f}",
            'cached': self.cache.stats()['cached'],
            'note': "Cached translations are FREE"
        }
    
    def get_stats(self) -> Dict:
        """Get usage statistics."""
        return {
            'provider': self.provider,
            'total_cost': f"${self.total_cost:.4f}",
            'cache': self.cache.stats()
        }


def interactive_ai_setup() -> Optional[AIMathTranslator]:
    """Interactive setup - simplified for OpenAI only."""
    print("\n" + "="*60)
    print("AI MATH TRANSLATION SETUP")
    print("="*60)
    
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("\nOPENAI_API_KEY not found!")
        print("Set it with: set OPENAI_API_KEY=your-key-here")
        api_key = input("\nOr enter your API key now (or press Enter to skip): ").strip()
        if not api_key:
            print("[INFO] AI fallback disabled.")
            return None
    
    translator = AIMathTranslator(api_key=api_key)
    available, msg = translator.is_available()
    
    print(f"\n[CHECK] {msg}")
    
    if not available:
        return None
    
    print(f"[OK] AI translation ready")
    print(f"[INFO] Cost: ~$0.003 per equation (cached translations are free)")
    
    return translator


def estimate_and_confirm(translator: AIMathTranslator, num_equations: int) -> bool:
    """Show estimate and get confirmation."""
    est = translator.estimate_cost(num_equations)
    
    print("\n" + "-"*40)
    print(f"Equations to translate: {est['equations']}")
    print(f"Cost per equation: {est['cost_per_equation']}")
    print(f"Total estimate: {est['total_estimate']}")
    print(f"Already cached: {est['cached']}")
    print("-"*40)
    
    response = input("\nProceed? (yes/no): ").strip().lower()
    return response in ['yes', 'y']


# Quick test
if __name__ == '__main__':
    print("Testing AI Math Translator...")
    
    translator = AIMathTranslator()
    available, msg = translator.is_available()
    print(f"Status: {msg}")
    
    if available:
        test_eq = r"$\Phi_{eff} = \Phi_{max} \cdot e^{-\alpha S}$"
        print(f"\nTest equation: {test_eq}")
        result = translator.translate(test_eq, "Sin-Impedance equation from H10")
        print(f"Translation: {result}")
        print(f"\nStats: {translator.get_stats()}")
