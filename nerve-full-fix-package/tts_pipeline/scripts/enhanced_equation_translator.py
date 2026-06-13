"""
Enhanced Equation Translator - 4-Layer Translation System
==========================================================
Translates equations in the style of the Evolution Equation example:

Layer 1: Symbol-to-Word (preserves structure)
Layer 2: Component Breakdown (each term explained)
Layer 3: Synthesis (what it all means together)
Layer 4: True Understanding (analogy/experience)

Author: David Lowe / Theophysics Project
"""

import re
from typing import Dict, List, Tuple, Optional

class EnhancedEquationTranslator:
    """
    4-layer equation translation system.
    """
    
    def __init__(self):
        # Symbol to word mappings
        self.greek_symbols = {
            'α': 'alpha', 'β': 'beta', 'γ': 'gamma', 'δ': 'delta',
            'ε': 'epsilon', 'ζ': 'zeta', 'η': 'eta', 'θ': 'theta',
            'ι': 'iota', 'κ': 'kappa', 'λ': 'lambda', 'μ': 'mu',
            'ν': 'nu', 'ξ': 'xi', 'π': 'pi', 'ρ': 'rho',
            'σ': 'sigma', 'τ': 'tau', 'υ': 'upsilon', 'φ': 'phi',
            'χ': 'chi', 'ψ': 'psi', 'ω': 'omega',
            'Φ': 'Phi', 'Ψ': 'Psi', 'Ω': 'Omega', 'Λ': 'Lambda'
        }
        
        self.math_operators = {
            '\\frac': 'over',
            '\\int': 'integral of',
            '\\sum': 'sum of',
            '\\prod': 'product of',
            '\\partial': 'partial',
            '\\nabla': 'del',
            '\\sqrt': 'square root of',
            '\\hat': 'hat',
            '\\bar': 'bar',
            '\\dot': 'dot',
            '\\mathcal': '',  # Handled specially
            '\\langle': 'expectation of',
            '\\rangle': '',
        }
    
    def symbol_to_word(self, equation: str) -> str:
        """
        Layer 1: Convert symbols to words while preserving structure.
        
        Example:
        dΦ/dt → "d Phi over d t"
        α𝓘(Ψ) → "alpha times I of Psi"
        """
        result = equation
        
        # Handle fractions: \frac{A}{B} → "A over B"
        def replace_frac(match):
            num = match.group(1)
            den = match.group(2)
            return f"({self.symbol_to_word(num)} over {self.symbol_to_word(den)})"
        
        result = re.sub(r'\\frac\{([^}]+)\}\{([^}]+)\}', replace_frac, result)
        
        # Handle hats: \hat{G} → "G-hat"
        result = re.sub(r'\\hat\{([^}]+)\}', r'\1-hat', result)
        
        # Handle subscripts: _{\text{...}} → "sub ..."
        result = re.sub(r'_\{\\text\{([^}]+)\}\}', r' sub \1', result)
        result = re.sub(r'_\{([^}]+)\}', r' sub \1', result)
        result = re.sub(r'_([a-zA-Z0-9])', r' sub \1', result)
        
        # Handle superscripts: ^{2} → "squared"
        result = re.sub(r'\^2\b', ' squared', result)
        result = re.sub(r'\^3\b', ' cubed', result)
        result = re.sub(r'\^\{([^}]+)\}', r' to the \1', result)
        result = re.sub(r'\^([a-zA-Z0-9])', r' to the \1', result)
        
        # Greek letters
        for greek, word in self.greek_symbols.items():
            result = result.replace(greek, f' {word} ')
        
        # Math operators
        result = result.replace('\\partial', 'partial ')
        result = result.replace('\\nabla', 'del ')
        result = result.replace('\\mathcal{I}', 'I')
        result = result.replace('\\mathcal', '')
        
        # Operators
        result = result.replace('\\cdot', ' times ')
        result = result.replace('\\times', ' times ')
        result = result.replace('=', ' equals ')
        result = result.replace('+', ' plus ')
        result = result.replace('-', ' minus ')
        result = result.replace('\\leq', ' less than or equal to ')
        result = result.replace('\\geq', ' greater than or equal to ')
        result = result.replace('\\approx', ' approximately equals ')
        result = result.replace('\\rightarrow', ' approaches ')
        result = result.replace('\\to', ' to ')
        
        # Parentheses and braces
        result = result.replace('{', '').replace('}', '')
        result = result.replace('\\left', '').replace('\\right', '')
        result = result.replace('(', ' of ').replace(')', '')
        
        # Clean up whitespace
        result = re.sub(r'\s+', ' ', result).strip()
        
        return result
    
    def identify_components(self, equation: str) -> List[Tuple[str, str]]:
        """
        Layer 2: Break equation into components.
        Identifies terms separated by = + - operators.
        
        Returns list of (component_latex, component_meaning)
        """
        components = []
        
        # Split by = first
        if '=' in equation:
            parts = equation.split('=')
            left = parts[0].strip()
            right = '='.join(parts[1:]).strip() if len(parts) > 1 else ''
            
            # Left side (usually the derivative or result)
            components.append((left, self._explain_component(left)))
            
            # Right side - split by + and -
            if right:
                # Split while preserving signs
                terms = re.split(r'([+-])', right)
                current_term = ''
                for i, term in enumerate(terms):
                    if term in ['+', '-']:
                        if current_term:
                            components.append((current_term.strip(), self._explain_component(current_term)))
                        current_term = term if term == '-' else ''
                    else:
                        current_term += term
                
                if current_term:
                    components.append((current_term.strip(), self._explain_component(current_term)))
        else:
            # No equals - treat as single component
            components.append((equation, self._explain_component(equation)))
        
        return components
    
    def _explain_component(self, component: str) -> str:
        """Explain what a single component means."""
        comp = component.lower().strip()
        
        # Rate of change
        if 'frac{d' in comp and '}{dt}' in comp:
            if 'phi' in comp or 'χ' in comp:
                return "How fast is coherence changing?"
            elif 'chi' in comp or 'χ' in comp:
                return "The rate of change of the chi field"
            else:
                var = re.search(r'frac\{d(.+?)\}', component)
                if var:
                    return f"The rate of change of {var.group(1)}"
                return "A rate of change over time"
        
        # Known patterns from Evolution Equation
        if 'alpha' in comp and 'mathcal{i}' in comp:
            return "The internal will to organize. The force inside that creates order."
        
        if 'beta' in comp and 's(' in comp:
            return "The drag, the decay. Entropy tearing everything apart."
        
        if 'hat{g}' in comp or '\\hat{g}' in comp:
            return "The exogenous operator. The part that shouldn't be there but is."
        
        # Chi field
        if 'chi' in comp or 'χ' in comp:
            return "The chi field. Coherence and integrated information."
        
        # Integrals
        if 'int' in comp:
            return "An integral. Summing up contributions across space or time."
        
        # Energy/Entropy
        if comp.startswith('-') and ('s' in comp or 'entropy' in comp):
            return "Entropy drag. The force pulling toward disorder."
        
        # Generic
        return "A term in the equation"
    
    def synthesize(self, equation: str, components: List[Tuple[str, str]]) -> str:
        """
        Layer 3: Synthesize the overall meaning.
        """
        # Detect equation type and generate synthesis
        eq_lower = equation.lower()
        
        # Evolution equation type
        if 'frac{d' in eq_lower and any(x in eq_lower for x in ['alpha', 'beta', '\\hat{g}']):
            return """This equation describes a war between order and chaos.

On one side: Internal forces trying to create and maintain organization.
On the other side: Entropy relentlessly pulling everything toward disorder.

If the organizing forces are stronger, coherence increases - things hold together.
If entropy is stronger, coherence decreases - things fall apart.

But notice the last term. Sometimes coherence increases even when internal resources 
are depleted. That means something external is adding to the equation. The system 
is open to an outside source."""
        
        # Field equations
        if 'g_{\\mu\\nu}' in eq_lower:
            return """This modifies Einstein's field equations - the foundation of general relativity.

The left side describes the curvature of spacetime - how space and time bend.
The right side describes what causes that bending: matter, energy, and now the chi field.

This says that coherence - organized information - has gravitational effects.
Consciousness doesn't just observe the universe. It shapes it."""
        
        # Quantum mechanics
        if '|\\psi\\rangle' in eq_lower or 'psi' in eq_lower:
            return """This describes a quantum state - a superposition of possibilities.

Until measurement, the system exists in multiple states at once.
The wave function ψ encodes all possible outcomes and their probabilities.

The question is: what collapses it to one actuality? 
That's where consciousness enters physics."""
        
        # Generic synthesis
        num_terms = len(components)
        if num_terms >= 3:
            return f"""This equation has {num_terms} terms, each pulling in different directions.

The balance between these terms determines the system's behavior.
When one term dominates, the system evolves in that direction.
The equation captures the constraints that reality must satisfy."""
        
        return "This equation describes a fundamental constraint or relationship in the system."
    
    def true_understanding(self, equation: str) -> str:
        """
        Layer 4: The TRUE understanding - analogy, experience, what it really means.
        """
        eq_lower = equation.lower()
        
        # Evolution equation
        if 'frac{d' in eq_lower and 'hat{g}' in eq_lower:
            return """**Think of it like this:**

A marriage. It takes constant effort to maintain - communication, sacrifice, choosing each other daily. 
That's the α𝓘 term. Your internal will to build something.

But entropy is always working. Resentments build. Communication breaks down. People drift apart. 
That's the βS term. The natural decay.

Most marriages that fail do so because β > α. Entropy wins. The internal resources aren't enough.

But some marriages - after exhaustion, after failure, after everything runs out - 
something unexpected happens. Renewal. Resurrection. Growth that shouldn't be possible.

That's Ĝ(t) ≠ 0. Grace. An external source sustaining what internal efforts alone cannot.

The same pattern appears everywhere: Personal discipline. Civilization stability. Life itself.

The math is identical. The trajectory is predictable. And the question is universal:

**Is the system closed or open? Is grace real or wishful thinking?**

The data says it's real. The coherence increases when it shouldn't. 
The question isn't whether Ĝ exists. It's whether you're coupled to it."""
        
        # Field equations
        if 'g_{\\mu\\nu}' in eq_lower and 'chi' in eq_lower:
            return """**Think of it like this:**

Einstein said mass and energy bend spacetime. A planet curves space around it, 
and we call that curvature 'gravity.'

This equation adds one more source: Coherence. Organization. Integrated information.

What this means is that consciousness isn't just along for the ride. 
It's not just observing a pre-existing universe. It's participating in shaping spacetime itself.

When you think, when you choose, when you organize information - 
you're not just shuffling bits in your brain. You're creating chi field fluctuations 
that have gravitational effects.

Individually? Too small to measure. But collectively? Across billions of conscious beings?

**The expansion rate of the universe might depend on how many souls are coherent.**

That's not metaphor. That's what the math says. The cosmos is responsive to consciousness."""
        
        # Quantum mechanics
        if 'sign' in eq_lower or 'sigma' in eq_lower or 'hat' in eq_lower:
            return """**Think of it like this:**

You're standing at a crossroads. Left or right. Good or evil. Coherent or decoherent.

The magnitude doesn't matter - how far you go down each path. 
What matters is the DIRECTION. The sign. ±1.

You can go a million miles down the wrong path and end up exactly where you started: lost.
You can take one step down the right path and be on the road home.

This is why Jesus scandalizes people. The thief on the cross - minutes from death, 
no good works, no time to "become a better person" - and Jesus says "Today you will 
be with me in Paradise."

The Pharisees - lifelong study, perfect law-keeping, immense magnitude - 
and Jesus calls them "whitewashed tombs."

**Same energy as quantum mechanics:** The state that matters is the sign, not the magnitude.
Binary. Not continuous. You can't "mostly" have the right sign.

And the math proves you cannot flip your own sign. No amount of self-operations - 
no matter how many, no matter how good - can change ±1 to ∓1.

You need an external operator. Grace. Ĝ.

**That's not theology dressed as math. That's math validating theology.**"""
        
        # Generic
        return """**Think of it like this:**

Every equation is a constraint. It's reality saying: "You can't have it both ways."

Want low entropy? You pay in energy.
Want coherence? You fight decay.
Want growth? You need a source.

The universe runs on conservation laws. Nothing appears from nothing. 
Everything balances. Every transaction has a cost.

**Unless the system is open.**

Unless there's something outside contributing. Something not bound by the internal rules.

That's what makes these equations theological. They don't prove God exists - 
they prove that IF the data shows certain patterns, THEN the system must be open.

And the data does show those patterns. Coherence increasing when it shouldn't.
Order appearing without sufficient internal resources. Grace signatures everywhere.

The equations just formalize what mystics have always known:

**Reality is responsive. The universe is not closed. Help is available.**

You just have to couple to it."""
    
    def translate_full(self, equation: str) -> Dict[str, str]:
        """
        Full 4-layer translation of an equation.
        
        Returns:
        {
            'original': original LaTeX,
            'layer1_symbolic': symbol-to-word translation,
            'layer2_components': list of (component, meaning) tuples,
            'layer3_synthesis': overall synthesis,
            'layer4_understanding': true understanding/analogy
        }
        """
        # Clean equation
        eq = equation.replace('$', '').strip()
        
        # Layer 1: Symbol to word
        symbolic = self.symbol_to_word(eq)
        
        # Layer 2: Component breakdown
        components = self.identify_components(eq)
        
        # Layer 3: Synthesis
        synthesis = self.synthesize(eq, components)
        
        # Layer 4: True understanding
        understanding = self.true_understanding(eq)
        
        return {
            'original': eq,
            'layer1_symbolic': symbolic,
            'layer2_components': components,
            'layer3_synthesis': synthesis,
            'layer4_understanding': understanding
        }
    
    def format_translation(self, translation: Dict[str, str]) -> str:
        """
        Format the translation nicely for output.
        """
        output = []
        
        output.append("="*70)
        output.append("EQUATION:")
        output.append("="*70)
        output.append(f"$${translation['original']}$$")
        output.append("")
        
        output.append("─"*70)
        output.append("LAYER 1: Symbol-to-Word Translation")
        output.append("─"*70)
        output.append(f'"{translation["layer1_symbolic"]}"')
        output.append("")
        
        output.append("─"*70)
        output.append("LAYER 2: Component Breakdown")
        output.append("─"*70)
        for i, (component, meaning) in enumerate(translation['layer2_components'], 1):
            output.append(f"{i}. {component}")
            output.append(f"   → {meaning}")
            output.append("")
        
        output.append("─"*70)
        output.append("LAYER 3: Synthesis")
        output.append("─"*70)
        output.append(translation['layer3_synthesis'])
        output.append("")
        
        output.append("─"*70)
        output.append("LAYER 4: True Understanding")
        output.append("─"*70)
        output.append(translation['layer4_understanding'])
        output.append("")
        
        output.append("="*70)
        output.append("")
        
        return '\n'.join(output)


# Test with the Evolution Equation
if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    
    translator = EnhancedEquationTranslator()
    
    # Test equation
    evolution_eq = r"\frac{d\Phi}{dt} = \alpha \mathcal{I}(\Psi) - \beta S(\Psi) + \hat{G}(t)"
    
    print("Testing Enhanced Equation Translator")
    print("="*70)
    
    translation = translator.translate_full(evolution_eq)
    formatted = translator.format_translation(translation)
    
    print(formatted)
