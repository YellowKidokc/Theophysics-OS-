"""
Paper Formatting GUI - 4-Layer Equation Translation
===================================================
Interactive GUI for formatting academic papers with enhanced equations.

Features:
- Auto-discovers papers in your folders
- Select multiple papers to format
- Paste custom paths
- Batch processing
- Progress tracking
- Cost estimation

Author: David Lowe / Theophysics Project
"""

import sys
import os
import time
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import threading

# Add to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from equation_formatter import EquationFormatter
import re

class PaperFormatterGUI:
    """GUI for formatting papers with enhanced equations."""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Paper Formatter - 4-Layer Equation Translation")
        self.root.geometry("900x700")
        
        # Data
        self.discovered_papers = []
        self.selected_papers = []
        self.formatter = EquationFormatter()
        
        # Setup UI
        self.setup_ui()
        
        # Discover papers on startup
        self.discover_papers()
    
    def setup_ui(self):
        """Create the UI layout."""
        
        # Title
        title_frame = tk.Frame(self.root, bg="#2c3e50", height=60)
        title_frame.pack(fill=tk.X, padx=0, pady=0)
        title_frame.pack_propagate(False)
        
        title_label = tk.Label(
            title_frame,
            text="📄 Paper Formatter - 4-Layer Equation Translation",
            font=("Segoe UI", 14, "bold"),
            bg="#2c3e50",
            fg="white"
        )
        title_label.pack(pady=15)
        
        # Main container
        main_frame = tk.Frame(self.root, padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Instructions
        instructions = tk.Label(
            main_frame,
            text="Select papers to format with enhanced equation translations\n"
                 "(Callout boxes, symbol-to-word, breakdown, synthesis, real understanding)",
            font=("Segoe UI", 9),
            fg="#555",
            justify=tk.LEFT
        )
        instructions.pack(anchor=tk.W, pady=(0, 10))
        
        # Discovered Papers Section
        discovered_label = tk.Label(
            main_frame,
            text="📚 Discovered Papers:",
            font=("Segoe UI", 10, "bold")
        )
        discovered_label.pack(anchor=tk.W, pady=(10, 5))
        
        # Papers listbox with scrollbar
        papers_frame = tk.Frame(main_frame)
        papers_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        papers_scrollbar = tk.Scrollbar(papers_frame)
        papers_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.papers_listbox = tk.Listbox(
            papers_frame,
            selectmode=tk.MULTIPLE,
            font=("Consolas", 9),
            yscrollcommand=papers_scrollbar.set,
            height=12
        )
        self.papers_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        papers_scrollbar.config(command=self.papers_listbox.yview)
        
        # Buttons frame
        buttons_frame = tk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, pady=(10, 10))
        
        select_all_btn = tk.Button(
            buttons_frame,
            text="Select All",
            command=self.select_all_papers,
            width=12
        )
        select_all_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        clear_btn = tk.Button(
            buttons_frame,
            text="Clear Selection",
            command=self.clear_selection,
            width=12
        )
        clear_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        browse_btn = tk.Button(
            buttons_frame,
            text="Browse File...",
            command=self.browse_file,
            width=12
        )
        browse_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        rescan_btn = tk.Button(
            buttons_frame,
            text="🔄 Rescan",
            command=self.discover_papers,
            width=12
        )
        rescan_btn.pack(side=tk.RIGHT)
        
        # Custom path entry
        custom_frame = tk.Frame(main_frame)
        custom_frame.pack(fill=tk.X, pady=(10, 10))
        
        custom_label = tk.Label(
            custom_frame,
            text="Or paste custom path:",
            font=("Segoe UI", 9)
        )
        custom_label.pack(side=tk.LEFT, padx=(0, 10))
        
        self.custom_path_entry = tk.Entry(custom_frame, font=("Consolas", 9))
        self.custom_path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        add_custom_btn = tk.Button(
            custom_frame,
            text="Add",
            command=self.add_custom_path,
            width=10
        )
        add_custom_btn.pack(side=tk.LEFT)
        
        # Process button
        self.process_btn = tk.Button(
            main_frame,
            text="✨ Format Selected Papers",
            command=self.start_formatting,
            font=("Segoe UI", 11, "bold"),
            bg="#27ae60",
            fg="white",
            height=2
        )
        self.process_btn.pack(fill=tk.X, pady=(10, 10))
        
        # Progress frame
        progress_frame = tk.Frame(main_frame)
        progress_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        
        progress_label = tk.Label(
            progress_frame,
            text="📊 Progress:",
            font=("Segoe UI", 9, "bold")
        )
        progress_label.pack(anchor=tk.W, pady=(0, 5))
        
        self.progress_text = scrolledtext.ScrolledText(
            progress_frame,
            height=8,
            font=("Consolas", 8),
            state=tk.DISABLED,
            bg="#f8f9fa"
        )
        self.progress_text.pack(fill=tk.BOTH, expand=True)
    
    def log(self, message):
        """Add message to progress log."""
        self.progress_text.config(state=tk.NORMAL)
        self.progress_text.insert(tk.END, message + "\n")
        self.progress_text.see(tk.END)
        self.progress_text.config(state=tk.DISABLED)
        self.root.update()
    
    def discover_papers(self):
        """Auto-discover markdown papers in common folders."""
        self.log("Scanning for papers...")
        
        # Common paper locations
        search_paths = [
            r"O:\_THEO\THEO\TM SUBSTACK\TM SUBSTACK\02_DRAFTING\_Archive",
            r"O:\_THEO\THEO\TM SUBSTACK\TM SUBSTACK\03_PUBLICATIONS",
            r"O:\Theophysics_Backend\TTS_Engines\TTS_Pipeline"
        ]
        
        discovered = []
        
        for search_path in search_paths:
            if os.path.exists(search_path):
                for root, dirs, files in os.walk(search_path):
                    for file in files:
                        if file.endswith('.md') and not file.endswith('_MTL.md'):
                            full_path = os.path.join(root, file)
                            # Check if it has equations
                            if self.has_equations(full_path):
                                discovered.append(full_path)
        
        self.discovered_papers = discovered
        
        # Update listbox
        self.papers_listbox.delete(0, tk.END)
        for paper in discovered:
            display_name = self.format_paper_name(paper)
            self.papers_listbox.insert(tk.END, display_name)
        
        self.log(f"✓ Found {len(discovered)} papers with equations")
    
    def has_equations(self, filepath):
        """Check if file has display math equations."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                return '$$' in content
        except:
            return False
    
    def format_paper_name(self, filepath):
        """Format paper name for display."""
        path = Path(filepath)
        parent = path.parent.name
        return f"{path.name} ({parent})"
    
    def select_all_papers(self):
        """Select all papers in listbox."""
        self.papers_listbox.select_set(0, tk.END)
    
    def clear_selection(self):
        """Clear selection."""
        self.papers_listbox.selection_clear(0, tk.END)
    
    def browse_file(self):
        """Browse for a file."""
        filepath = filedialog.askopenfilename(
            title="Select Paper to Format",
            filetypes=[("Markdown files", "*.md"), ("All files", "*.*")]
        )
        if filepath:
            self.custom_path_entry.delete(0, tk.END)
            self.custom_path_entry.insert(0, filepath)
            self.add_custom_path()
    
    def add_custom_path(self):
        """Add custom path to selection."""
        path = self.custom_path_entry.get().strip()
        if path and os.path.exists(path):
            if path not in self.discovered_papers:
                self.discovered_papers.append(path)
                display_name = self.format_paper_name(path)
                self.papers_listbox.insert(tk.END, display_name)
                # Select the newly added item
                self.papers_listbox.select_set(tk.END)
                self.log(f"✓ Added: {Path(path).name}")
            else:
                self.log(f"Already in list: {Path(path).name}")
            self.custom_path_entry.delete(0, tk.END)
        else:
            messagebox.showerror("Error", "File not found!")
    
    def start_formatting(self):
        """Start formatting selected papers."""
        # Get selected indices
        selected_indices = self.papers_listbox.curselection()
        
        if not selected_indices:
            messagebox.showwarning("No Selection", "Please select at least one paper to format.")
            return
        
        # Get selected papers
        selected_papers = [self.discovered_papers[i] for i in selected_indices]
        
        # Confirm
        paper_names = [Path(p).name for p in selected_papers]
        message = f"Format {len(selected_papers)} paper(s)?\n\n" + "\n".join(f"• {n}" for n in paper_names)
        message += f"\n\nEstimated cost: $0.00 (built-in translations)"
        
        if not messagebox.askyesno("Confirm", message):
            return
        
        # Disable button
        self.process_btn.config(state=tk.DISABLED)
        
        # Run in thread
        thread = threading.Thread(target=self.format_papers, args=(selected_papers,))
        thread.start()
    
    def format_papers(self, papers):
        """Format the papers (runs in thread)."""
        self.log("="*60)
        self.log("STARTING BATCH FORMATTING")
        self.log("="*60)
        
        total = len(papers)
        success = 0
        
        for i, paper_path in enumerate(papers, 1):
            paper_name = Path(paper_path).name
            self.log(f"\n[{i}/{total}] Processing: {paper_name}")
            
            try:
                # Read
                with open(paper_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Count equations
                eq_count = len(re.findall(r'\$\$(.*?)\$\$', content, re.DOTALL))
                self.log(f"  Found {eq_count} equations")
                
                # Format
                self.log(f"  Formatting...")
                formatted = self.formatter.process_document(content, use_ai=False)
                
                # Save
                output_path = paper_path.replace('.md', '_MTL.md')
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(formatted)
                
                self.log(f"  ✓ Saved: {Path(output_path).name}")
                success += 1
                
            except Exception as e:
                self.log(f"  ✗ ERROR: {str(e)}")
        
        # Summary
        self.log("\n" + "="*60)
        self.log("COMPLETE!")
        self.log("="*60)
        self.log(f"✓ Successfully formatted: {success}/{total} papers")
        self.log(f"✓ Total cost: $0.00")
        self.log("="*60)
        
        # Re-enable button
        self.process_btn.config(state=tk.NORMAL)
        
        # Show completion message
        messagebox.showinfo(
            "Complete!",
            f"Successfully formatted {success}/{total} papers!\n\n"
            "Output files saved with '_MTL.md' suffix."
        )
    
    def run(self):
        """Run the GUI."""
        self.root.mainloop()


def main():
    """Launch the GUI."""
    app = PaperFormatterGUI()
    app.run()


if __name__ == '__main__':
    main()
