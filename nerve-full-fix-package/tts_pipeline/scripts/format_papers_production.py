"""
PRODUCTION Paper Formatter - Math Translation Layer
====================================================
Production-grade tool for processing 31,000+ documents.

FEATURES:
- Checkpoint/resume (survives reboots)
- Error resilience (keeps going)
- Progress tracking
- Essential code only
- Comprehensive logging

Author: David Lowe / Theophysics Project
"""

import sys
import os
import json
import time
import traceback
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from equation_formatter import EquationFormatter
import re

class ProductionPaperFormatter:
    """Production-grade paper formatter with checkpoint/resume."""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Paper Formatter - PRODUCTION")
        self.root.geometry("1000x750")
        
        self.formatter = EquationFormatter()
        self.checkpoint_file = "paper_formatter_checkpoint.json"
        self.log_file = "paper_formatter_log.txt"
        
        # State
        self.discovered_papers = []
        self.checkpoint_data = self.load_checkpoint()
        self.is_processing = False
        
        self.setup_ui()
        self.discover_papers()
        
        # Check for resume
        if self.checkpoint_data.get('in_progress'):
            self.prompt_resume()
    
    def setup_ui(self):
        """Minimal, essential UI."""
        
        # Title bar
        title_frame = tk.Frame(self.root, bg="#c0392b", height=70)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)
        
        title = tk.Label(
            title_frame,
            text="PRODUCTION Paper Formatter - 31K+ Documents",
            font=("Segoe UI", 16, "bold"),
            bg="#c0392b",
            fg="white"
        )
        title.pack(pady=20)
        
        # Main area
        main = tk.Frame(self.root, padx=20, pady=20)
        main.pack(fill=tk.BOTH, expand=True)
        
        # Status
        status_frame = tk.Frame(main)
        status_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.status_label = tk.Label(
            status_frame,
            text="Ready. Select papers and click START.",
            font=("Segoe UI", 10),
            fg="#27ae60"
        )
        self.status_label.pack(side=tk.LEFT)
        
        self.stats_label = tk.Label(
            status_frame,
            text="",
            font=("Consolas", 9),
            fg="#555"
        )
        self.stats_label.pack(side=tk.RIGHT)
        
        # Papers list
        tk.Label(
            main,
            text="Papers Found:",
            font=("Segoe UI", 10, "bold")
        ).pack(anchor=tk.W, pady=(10, 5))
        
        list_frame = tk.Frame(main)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.papers_listbox = tk.Listbox(
            list_frame,
            selectmode=tk.MULTIPLE,
            font=("Consolas", 9),
            yscrollcommand=scrollbar.set,
            height=15
        )
        self.papers_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.papers_listbox.yview)
        
        # Buttons
        btn_frame = tk.Frame(main)
        btn_frame.pack(fill=tk.X, pady=(10, 10))
        
        tk.Button(
            btn_frame,
            text="Select All",
            command=self.select_all,
            width=12
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        tk.Button(
            btn_frame,
            text="Clear",
            command=self.clear_selection,
            width=12
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        tk.Button(
            btn_frame,
            text="Rescan",
            command=self.discover_papers,
            width=12
        ).pack(side=tk.LEFT, padx=(0, 20))
        
        self.start_btn = tk.Button(
            btn_frame,
            text="START PROCESSING",
            command=self.start_processing,
            font=("Segoe UI", 11, "bold"),
            bg="#27ae60",
            fg="white",
            width=20,
            height=2
        )
        self.start_btn.pack(side=tk.RIGHT)
        
        # Log
        tk.Label(
            main,
            text="Log:",
            font=("Segoe UI", 9, "bold")
        ).pack(anchor=tk.W, pady=(10, 5))
        
        self.log_text = scrolledtext.ScrolledText(
            main,
            height=12,
            font=("Consolas", 8),
            bg="#f8f9fa",
            state=tk.DISABLED
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)
    
    def log(self, message, level="INFO"):
        """Thread-safe logging."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_line = f"[{timestamp}] {level}: {message}"
        
        # UI log
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, log_line + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        
        # File log
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(log_line + "\n")
        except:
            pass
        
        self.root.update()
    
    def load_checkpoint(self):
        """Load checkpoint data."""
        if os.path.exists(self.checkpoint_file):
            try:
                with open(self.checkpoint_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def save_checkpoint(self, data):
        """Save checkpoint data."""
        try:
            with open(self.checkpoint_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self.log(f"Failed to save checkpoint: {e}", "WARN")
    
    def prompt_resume(self):
        """Ask if user wants to resume."""
        completed = self.checkpoint_data.get('completed', 0)
        total = self.checkpoint_data.get('total', 0)
        
        if total > 0:
            msg = f"Previous session interrupted.\n\n"
            msg += f"Progress: {completed}/{total} papers\n\n"
            msg += "Resume from where you left off?"
            
            if messagebox.askyesno("Resume?", msg):
                self.log(f"Resuming from checkpoint: {completed}/{total}")
            else:
                self.checkpoint_data = {}
                self.save_checkpoint({})
    
    def discover_papers(self):
        """Scan for papers with equations."""
        self.log("Scanning for papers...")
        
        search_paths = [
            r"O:\_THEO\THEO\TM SUBSTACK\TM SUBSTACK\02_DRAFTING\_Archive",
            r"O:\_THEO\THEO\TM SUBSTACK\TM SUBSTACK\03_PUBLICATIONS",
        ]
        
        found = []
        
        for search_path in search_paths:
            if not os.path.exists(search_path):
                continue
            
            try:
                for root, dirs, files in os.walk(search_path):
                    for file in files:
                        if file.endswith('.md') and not file.endswith('_MTL.md'):
                            full_path = os.path.join(root, file)
                            if self.has_equations(full_path):
                                found.append(full_path)
            except Exception as e:
                self.log(f"Error scanning {search_path}: {e}", "WARN")
        
        self.discovered_papers = sorted(found)
        
        # Update UI
        self.papers_listbox.delete(0, tk.END)
        for paper in self.discovered_papers:
            display = f"{Path(paper).name} ({Path(paper).parent.name})"
            self.papers_listbox.insert(tk.END, display)
        
        self.log(f"Found {len(found)} papers with equations")
        self.stats_label.config(text=f"{len(found)} papers")
    
    def has_equations(self, filepath):
        """Check if file has equations."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read(50000)  # First 50KB
                return '$$' in content
        except:
            return False
    
    def select_all(self):
        self.papers_listbox.select_set(0, tk.END)
    
    def clear_selection(self):
        self.papers_listbox.selection_clear(0, tk.END)
    
    def start_processing(self):
        """Start batch processing."""
        if self.is_processing:
            return
        
        # Get selection
        selected_idx = self.papers_listbox.curselection()
        if not selected_idx:
            messagebox.showwarning("No Selection", "Select papers to process.")
            return
        
        selected_papers = [self.discovered_papers[i] for i in selected_idx]
        
        # Confirm
        msg = f"Process {len(selected_papers)} papers?\n\n"
        msg += "This will:\n"
        msg += "- Create _MTL.md versions\n"
        msg += "- Save checkpoint after each file\n"
        msg += "- Continue on errors\n"
        msg += "- Survive reboots\n\n"
        msg += "Cost: $0.00 (FREE)"
        
        if not messagebox.askyesno("Confirm", msg):
            return
        
        # Disable UI
        self.start_btn.config(state=tk.DISABLED, text="PROCESSING...")
        self.is_processing = True
        
        # Process in thread
        thread = threading.Thread(
            target=self.process_papers,
            args=(selected_papers,),
            daemon=True
        )
        thread.start()
    
    def process_papers(self, papers):
        """Process papers with checkpoint/resume."""
        
        # Initialize checkpoint
        if not self.checkpoint_data.get('in_progress'):
            self.checkpoint_data = {
                'in_progress': True,
                'total': len(papers),
                'completed': 0,
                'failed': 0,
                'papers': papers,
                'completed_files': [],
                'failed_files': []
            }
            self.save_checkpoint(self.checkpoint_data)
        else:
            # Resume
            papers = self.checkpoint_data['papers']
        
        total = len(papers)
        completed = self.checkpoint_data['completed']
        failed = self.checkpoint_data['failed']
        
        self.log("="*60)
        self.log("PRODUCTION BATCH PROCESSING")
        self.log("="*60)
        self.log(f"Total: {total} | Starting at: {completed+1}")
        
        start_time = time.time()
        
        # Process from checkpoint
        for i in range(completed, total):
            paper_path = papers[i]
            paper_name = Path(paper_path).name
            
            # Check if already done (resume case)
            if paper_path in self.checkpoint_data.get('completed_files', []):
                self.log(f"[{i+1}/{total}] SKIP: {paper_name} (already done)")
                continue
            
            self.log(f"[{i+1}/{total}] Processing: {paper_name}")
            self.status_label.config(text=f"Processing {i+1}/{total}: {paper_name}")
            
            try:
                # Read
                with open(paper_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Count equations
                eq_count = len(re.findall(r'\$\$(.*?)\$\$', content, re.DOTALL))
                self.log(f"  Found {eq_count} equations")
                
                # Format
                formatted = self.formatter.process_document(content, use_ai=False)
                
                # Save
                output_path = paper_path.replace('.md', '_MTL.md')
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(formatted)
                
                self.log(f"  SUCCESS: {Path(output_path).name}")
                
                # Update checkpoint
                self.checkpoint_data['completed'] = i + 1
                self.checkpoint_data['completed_files'].append(paper_path)
                self.save_checkpoint(self.checkpoint_data)
                
            except Exception as e:
                self.log(f"  ERROR: {str(e)}", "ERROR")
                self.log(f"  Stack: {traceback.format_exc()}", "DEBUG")
                
                # Update checkpoint
                self.checkpoint_data['failed'] += 1
                self.checkpoint_data['failed_files'].append({
                    'file': paper_path,
                    'error': str(e)
                })
                self.save_checkpoint(self.checkpoint_data)
                
                # CONTINUE - don't stop batch
                continue
        
        # Complete
        elapsed = time.time() - start_time
        completed = self.checkpoint_data['completed']
        failed = self.checkpoint_data['failed']
        
        self.log("="*60)
        self.log("COMPLETE!")
        self.log("="*60)
        self.log(f"Success: {completed}/{total}")
        self.log(f"Failed: {failed}/{total}")
        self.log(f"Time: {elapsed:.1f}s")
        self.log(f"Cost: $0.00")
        self.log("="*60)
        
        # Clear checkpoint
        self.checkpoint_data = {}
        self.save_checkpoint({})
        
        # Re-enable UI
        self.start_btn.config(state=tk.NORMAL, text="START PROCESSING")
        self.is_processing = False
        self.status_label.config(text="Complete!")
        self.stats_label.config(text=f"Done: {completed}/{total}")
        
        # Show summary
        msg = f"Processing complete!\n\n"
        msg += f"Success: {completed}/{total}\n"
        msg += f"Failed: {failed}/{total}\n"
        msg += f"Time: {elapsed:.1f}s\n"
        msg += f"Cost: $0.00\n\n"
        msg += f"Output files: *_MTL.md"
        
        messagebox.showinfo("Complete", msg)
    
    def run(self):
        """Run the GUI."""
        self.root.mainloop()


def main():
    app = ProductionPaperFormatter()
    app.run()


if __name__ == '__main__':
    main()
