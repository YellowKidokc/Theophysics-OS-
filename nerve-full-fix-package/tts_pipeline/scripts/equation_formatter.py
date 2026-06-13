"""
Complete Equation Formatting System
====================================
Formats equations with:
1. Centered callout box
2. Symbol-to-word translation (preserves structure)
3. Component breakdown
4. Synthesis
5. True understanding (with optional AI)

Author: David Lowe / Theophysics Project
"""

import re
from typing import Dict, List, Optional
from enhanced_equation_translator import EnhancedEquationTranslator

class EquationFormatter:
    """Formats equations beautifully for markdown output."""
    
    def __init__(self, ai_translator=None):
        self.translator = EnhancedEquationTranslator()
        self.ai_translator = ai_translator
    
    def create_callout_box(self, equation: str, title: str = "EQUATION") -> str:
        """
        Create a centered callout box for the equation.
        Uses markdown blockquote with custom styling.
        """
        lines = [
            "",
            f"> **{title}**",
            "> ",
            f"> $${equation}$$",
            ">",
            ""
        ]
        return '\n'.join(lines)
    
    def format_symbol_to_word(self, symbolic_translation: str) -> str:
        """
        Format the symbol-to-word translation to look like an equation structure.
        Preserves mathematical appearance but in English.
        """
        lines = [
            "",
            "**Reading it in words:**",
            "",
            f"*\"{symbolic_translation}\"*",
            ""
        ]
        return '\n'.join(lines)
    
    def format_component_breakdown(self, components: List[tuple]) -> str:
        """Format the component breakdown nicely."""
        lines = [
            "",
            "**Breaking it down:**",
            ""
        ]
        
        for i, (component, meaning) in enumerate(components, 1):
            # Show component with its meaning
            lines.append(f"{i}. `{component}`")
            lines.append(f"   → *{meaning}*")
            lines.append("")
        
        return '\n'.join(lines)
    
    def format_synthesis(self, synthesis: str) -> str:
        """Format the synthesis section."""
        lines = [
            "",
            "**What it all means:**",
            "",
            synthesis,
            ""
        ]
        return '\n'.join(lines)
    
    def format_true_understanding(self, understanding: str) -> str:
        """Format the true understanding/analogy section."""
        lines = [
            "",
            "**The real picture:**",
            "",
            understanding,
            ""
        ]
        return '\n'.join(lines)
    
    def format_complete_equation(self, equation: str, 
                                 title: str = "EQUATION",
                                 use_ai_for_understanding: bool = False) -> str:
        """
        Complete formatting pipeline for an equation.
        
        Args:
            equation: LaTeX equation (without $$)
            title: Title for the callout box
            use_ai_for_understanding: Whether to use AI for deeper explanations
        
        Returns:
            Beautifully formatted markdown with all layers
        """
        output = []
        
        # Get translation
        translation = self.translator.translate_full(equation)
        
        # 1. Callout box with equation
        output.append(self.create_callout_box(equation, title))
        
        # 2. Symbol-to-word translation
        output.append(self.format_symbol_to_word(translation['layer1_symbolic']))
        
        # 3. Component breakdown
        output.append(self.format_component_breakdown(translation['layer2_components']))
        
        # 4. Synthesis
        output.append(self.format_synthesis(translation['layer3_synthesis']))
        
        # 5. True understanding
        # If AI is enabled and available, enhance this section
        if use_ai_for_understanding and self.ai_translator:
            try:
                ai_understanding = self.ai_translator.translate_equation(equation)
                if ai_understanding:
                    output.append(self.format_true_understanding(ai_understanding))
                else:
                    output.append(self.format_true_understanding(translation['layer4_understanding']))
            except Exception as e:
                print(f"[WARN] AI enhancement failed: {e}")
                output.append(self.format_true_understanding(translation['layer4_understanding']))
        else:
            output.append(self.format_true_understanding(translation['layer4_understanding']))
        
        # Add separator
        output.append("---")
        output.append("")
        
        return '\n'.join(output)
    
    def process_document(self, content: str, use_ai: bool = False) -> str:
        """
        Process an entire document, formatting all equations.
        ERROR RESILIENT: If one equation fails, continue with others.
        
        Args:
            content: Markdown content with equations
            use_ai: Whether to use AI for enhanced explanations
        
        Returns:
            Document with all equations beautifully formatted
        """
        # Find all display math equations
        pattern = r'\$\$(.*?)\$\$'
        
        def replace_equation(match):
            equation = match.group(1).strip()
            
            # Skip very short equations (likely inline numbers)
            if len(equation) < 5:
                return match.group(0)
            
            # Format with full treatment - ERROR HANDLING
            try:
                formatted = self.format_complete_equation(
                    equation, 
                    title="EQUATION",
                    use_ai_for_understanding=use_ai
                )
                return formatted
            except Exception as e:
                # If formatting fails, return original equation
                print(f"[WARN] Failed to format equation: {e}")
                return match.group(0)  # Return original
        
        # Replace all equations
        try:
            result = re.sub(pattern, replace_equation, content, flags=re.DOTALL)
            return result
        except Exception as e:
            # If document processing fails completely, return original
            print(f"[ERROR] Document processing failed: {e}")
            return content


def test_formatter():
    """Test the formatter with the Evolution Equation."""
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    
    formatter = EquationFormatter()
    
    # Test equation
    evolution_eq = r"\frac{d\Phi}{dt} = \alpha \mathcal{I}(\Psi) - \beta S(\Psi) + \hat{G}(t)"
    
    print("="*70)
    print("TESTING EQUATION FORMATTER")
    print("="*70)
    print()
    
    formatted = formatter.format_complete_equation(evolution_eq, title="THE EVOLUTION EQUATION")
    
    print(formatted)
    
    # Save to file
    with open('formatted_equation_example.md', 'w', encoding='utf-8') as f:
        f.write("# Example Formatted Equation\n\n")
        f.write(formatted)
    
    print("="*70)
    print("Saved to: formatted_equation_example.md")
    print("="*70)


if __name__ == '__main__':
    test_formatter()
