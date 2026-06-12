"""
Math Translation Manager with Checkpoint/Resume System
======================================================
GUI tool for batch processing folders with math translation layer.
Features:
  - Folder selection interface
  - Progress tracking (e.g., 35 of 159)
  - Checkpoint system for graceful shutdown/resume
  - Automatic cleanup of incomplete files
  - Uses consolidated MATH_TRANSLATION_MASTER.xlsx

Author: David Lowe / Theophysics Project
"""

import os
import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from pathlib import Path
from datetime import datetime
import pandas as pd
import asyncio
import threading
from typing import Dict, List, Optional
from tts_pipeline import TTSPipeline
from theophysics_normalizer import TheophysicsNormalizer
try:
    from ai_math_translator import AIMathTranslator, interactive_ai_setup, estimate_and_confirm
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False
    print("[INFO] AI translation fallback not available")

class CheckpointManager:
    """Manages checkpoints for graceful shutdown and resume."""
    
    def __init__(self, checkpoint_dir: str = ".checkpoints"):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(exist_ok=True)
    
    def save_checkpoint(self, job_id: str, data: dict):
        """Save checkpoint data."""
        checkpoint_file = self.checkpoint_dir / f"{job_id}.json"
        with open(checkpoint_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    
    def load_checkpoint(self, job_id: str) -> Optional[dict]:
        """Load checkpoint data."""
        checkpoint_file = self.checkpoint_dir / f"{job_id}.json"
        if checkpoint_file.exists():
            with open(checkpoint_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
    
    def delete_checkpoint(self, job_id: str):
        """Delete checkpoint after successful completion."""
        checkpoint_file = self.checkpoint_dir / f"{job_id}.json"
        if checkpoint_file.exists():
            checkpoint_file.unlink()
    
    def list_checkpoints(self) -> List[str]:
        """List all available checkpoints."""
        return [f.stem for f in self.checkpoint_dir.glob("*.json")]

class MathTranslationProcessor:
    """Processes files with math translation layer and checkpoint support."""
    
    def __init__(self, master_excel_path: str = "MATH_TRANSLATION_MASTER.xlsx", 
                 ai_translator: Optional['AIMathTranslator'] = None):
        self.master_excel_path = master_excel_path
        self.translations = self.load_translations()
        self.ai_translator = ai_translator
        self.normalizer = TheophysicsNormalizer(ai_translator=ai_translator)
        self.checkpoint_mgr = CheckpointManager()
        
        # Stats
        self.total_files = 0
        self.processed_count = 0
        self.failed_count = 0
        self.skipped_count = 0
        
        # Control flags
        self.should_stop = False
        self.current_file = None
    
    def load_translations(self) -> Dict[str, dict]:
        """Load translations from master Excel file."""
        translations = {}
        
        if not os.path.exists(self.master_excel_path):
            print(f"[WARN] Master Excel not found: {self.master_excel_path}")
            return translations
        
        try:
            df = pd.read_excel(self.master_excel_path)
            print(f"[INFO] Loaded {len(df)} translations from master file")
            
            for _, row in df.iterrows():
                latex = str(row.get('latex', '')).strip()
                if latex and latex != 'nan':
                    translations[latex] = {
                        'tts_audio': str(row.get('tts_audio', '')).strip(),
                        'short_form': str(row.get('short_form', '')).strip(),
                        'medium_form': str(row.get('medium_form', '')).strip(),
                        'conceptual_meaning': str(row.get('conceptual_meaning', '')).strip(),
                        'paper_ref': str(row.get('paper_ref', '')).strip()
                    }
            
            return translations
        except Exception as e:
            print(f"[ERROR] Failed to load translations: {e}")
            return translations
    
    def discover_files(self, input_dir: str) -> List[Path]:
        """Find all processable files (.md, .txt) in directory."""
        files = []
        for root, dirs, filenames in os.walk(input_dir):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for filename in filenames:
                if filename.lower().endswith(('.md', '.txt')):
                    files.append(Path(root) / filename)
        return sorted(files)
    
    def generate_job_id(self, input_dir: str) -> str:
        """Generate unique job ID based on input directory."""
        from hashlib import md5
        dir_hash = md5(str(input_dir).encode()).hexdigest()[:8]
        return f"job_{dir_hash}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    def process_batch(self, input_dir: str, output_dir: str, 
                      resume_job_id: Optional[str] = None,
                      progress_callback=None) -> dict:
        """
        Process all files in a directory with checkpoint support.
        
        Args:
            input_dir: Input directory path
            output_dir: Output directory path
            resume_job_id: Job ID to resume (optional)
            progress_callback: Callback function(current, total, filename) for progress updates
        
        Returns:
            dict: Statistics about the batch processing
        """
        
        # Generate or use existing job ID
        if resume_job_id:
            job_id = resume_job_id
            checkpoint = self.checkpoint_mgr.load_checkpoint(job_id)
            if not checkpoint:
                raise ValueError(f"No checkpoint found for job: {resume_job_id}")
            print(f"[RESUME] Resuming job: {job_id}")
        else:
            job_id = self.generate_job_id(input_dir)
            checkpoint = None
            print(f"[NEW JOB] Starting: {job_id}")
        
        # Discover files
        files = self.discover_files(input_dir)
        self.total_files = len(files)
        
        if self.total_files == 0:
            return {
                'job_id': job_id,
                'total': 0,
                'processed': 0,
                'failed': 0,
                'skipped': 0,
                'status': 'no_files'
            }
        
        # Resume from checkpoint or start fresh
        if checkpoint:
            self.processed_count = checkpoint.get('processed_count', 0)
            self.failed_count = checkpoint.get('failed_count', 0)
            self.skipped_count = checkpoint.get('skipped_count', 0)
            processed_files = set(checkpoint.get('processed_files', []))
            print(f"[RESUME] Starting from file {self.processed_count + 1} of {self.total_files}")
        else:
            self.processed_count = 0
            self.failed_count = 0
            self.skipped_count = 0
            processed_files = set()
        
        # Ensure output directory exists
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # Process each file
        for i, file_path in enumerate(files):
            # Check if already processed
            if str(file_path) in processed_files:
                self.skipped_count += 1
                continue
            
            # Check stop flag
            if self.should_stop:
                print(f"[STOP] Graceful shutdown at file {i + 1} of {self.total_files}")
                # Save checkpoint
                self.checkpoint_mgr.save_checkpoint(job_id, {
                    'input_dir': str(input_dir),
                    'output_dir': str(output_dir),
                    'total_files': self.total_files,
                    'processed_count': self.processed_count,
                    'failed_count': self.failed_count,
                    'skipped_count': self.skipped_count,
                    'processed_files': list(processed_files),
                    'last_file': str(file_path),
                    'timestamp': datetime.now().isoformat()
                })
                return {
                    'job_id': job_id,
                    'total': self.total_files,
                    'processed': self.processed_count,
                    'failed': self.failed_count,
                    'skipped': self.skipped_count,
                    'status': 'interrupted',
                    'checkpoint_saved': True
                }
            
            # Update current file
            self.current_file = str(file_path)
            
            # Progress callback
            if progress_callback:
                progress_callback(i + 1, self.total_files, file_path.name)
            
            # Process file
            try:
                output_path = Path(output_dir) / file_path.name
                success = self.process_single_file(file_path, output_path)
                
                if success:
                    self.processed_count += 1
                    processed_files.add(str(file_path))
                else:
                    self.failed_count += 1
                
            except Exception as e:
                print(f"[ERROR] {file_path.name}: {e}")
                self.failed_count += 1
        
        # Job complete - delete checkpoint
        self.checkpoint_mgr.delete_checkpoint(job_id)
        
        return {
            'job_id': job_id,
            'total': self.total_files,
            'processed': self.processed_count,
            'failed': self.failed_count,
            'skipped': self.skipped_count,
            'status': 'completed'
        }
    
    def process_single_file(self, input_path: Path, output_path: Path) -> bool:
        """Process a single file with math translation."""
        try:
            # Read file
            with open(input_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Apply normalization
            normalized = self.normalizer.normalize(content)
            
            # Save normalized output
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(normalized)
            
            return True
            
        except Exception as e:
            print(f"[ERROR] Failed to process {input_path.name}: {e}")
            # Clean up incomplete file
            if output_path.exists():
                output_path.unlink()
            return False
    
    def stop(self):
        """Signal to stop processing gracefully."""
        self.should_stop = True

class MathTranslationGUI:
    """GUI for Math Translation Manager."""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Math Translation Manager")
        self.root.geometry("800x600")
        
        self.ai_translator = None  # Will be set if user enables AI
        self.processor = None  # Will be created after AI setup
        self.current_thread = None
        
        self.setup_ui()
        self.show_ai_setup_option()
        self.check_for_checkpoints()
    
    def setup_ui(self):
        """Setup the GUI interface."""
        
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Title
        title = ttk.Label(main_frame, text="Math Translation Layer Processor", 
                         font=('Arial', 16, 'bold'))
        title.grid(row=0, column=0, columnspan=3, pady=10)
        
        # Input directory selection
        ttk.Label(main_frame, text="Input Directory:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.input_dir_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.input_dir_var, width=50).grid(row=1, column=1, pady=5)
        ttk.Button(main_frame, text="Browse...", command=self.browse_input).grid(row=1, column=2, pady=5)
        
        # Output directory selection
        ttk.Label(main_frame, text="Output Directory:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.output_dir_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.output_dir_var, width=50).grid(row=2, column=1, pady=5)
        ttk.Button(main_frame, text="Browse...", command=self.browse_output).grid(row=2, column=2, pady=5)
        
        # Progress bar
        ttk.Label(main_frame, text="Progress:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.progress_var, 
                                           maximum=100, length=400)
        self.progress_bar.grid(row=3, column=1, columnspan=2, pady=5, sticky=(tk.W, tk.E))
        
        # Status label
        self.status_var = tk.StringVar(value="Ready")
        status_label = ttk.Label(main_frame, textvariable=self.status_var, font=('Arial', 10))
        status_label.grid(row=4, column=0, columnspan=3, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=5, column=0, columnspan=3, pady=10)
        
        self.start_btn = ttk.Button(button_frame, text="Start Processing", 
                                     command=self.start_processing)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_btn = ttk.Button(button_frame, text="Stop", 
                                    command=self.stop_processing, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        
        self.resume_btn = ttk.Button(button_frame, text="Resume Checkpoint", 
                                      command=self.resume_processing, state=tk.DISABLED)
        self.resume_btn.pack(side=tk.LEFT, padx=5)
        
        # Log area
        ttk.Label(main_frame, text="Log:").grid(row=6, column=0, sticky=tk.W, pady=5)
        self.log_text = scrolledtext.ScrolledText(main_frame, width=80, height=15, 
                                                   font=('Consolas', 9))
        self.log_text.grid(row=7, column=0, columnspan=3, pady=5, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(7, weight=1)
    
    def show_ai_setup_option(self):
        """Show AI setup option dialog if available."""
        if not AI_AVAILABLE:
            self.processor = MathTranslationProcessor()
            return
        
        # Ask user if they want AI fallback
        response = messagebox.askyesno(
            "AI Translation Fallback",
            "Enable AI translation for equations not in master file?\n\n"
            "You'll be able to choose:\n"
            "- OpenAI GPT-3.5 (cheap: ~$0.003/equation)\n"
            "- OpenAI GPT-4 (best: ~$0.09/equation)\n"
            "- LLaMA via Ollama (FREE, local)\n\n"
            "Translations are cached - only pay once per unique equation."
        )
        
        if response:
            self.log("AI translation fallback requested...")
            self.log("Opening AI setup dialog...")
            
            # Run interactive setup in separate thread so GUI doesn't freeze
            import threading
            def setup_ai():
                translator = interactive_ai_setup()
                if translator:
                    self.ai_translator = translator
                    self.root.after(0, lambda: self.log(f"[OK] AI fallback enabled: {translator.provider}"))
                else:
                    self.root.after(0, lambda: self.log("[INFO] AI fallback disabled"))
                
                # Create processor with or without AI
                self.processor = MathTranslationProcessor(ai_translator=self.ai_translator)
            
            threading.Thread(target=setup_ai, daemon=True).start()
        else:
            self.log("[INFO] AI fallback disabled")
            self.processor = MathTranslationProcessor()
    
    def browse_input(self):
        """Browse for input directory."""
        directory = filedialog.askdirectory(title="Select Input Directory")
        if directory:
            self.input_dir_var.set(directory)
    
    def browse_output(self):
        """Browse for output directory."""
        directory = filedialog.askdirectory(title="Select Output Directory")
        if directory:
            self.output_dir_var.set(directory)
    
    def log(self, message: str):
        """Add message to log."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.root.update()
    
    def update_progress(self, current: int, total: int, filename: str):
        """Update progress bar and status."""
        progress = (current / total) * 100
        self.progress_var.set(progress)
        self.status_var.set(f"Processing {current} of {total}: {filename}")
        self.log(f"Processing ({current}/{total}): {filename}")
    
    def check_for_checkpoints(self):
        """Check if there are any saved checkpoints."""
        checkpoints = self.processor.checkpoint_mgr.list_checkpoints()
        if checkpoints:
            self.resume_btn.config(state=tk.NORMAL)
            self.log(f"Found {len(checkpoints)} checkpoint(s) available for resume")
    
    def start_processing(self):
        """Start processing files."""
        input_dir = self.input_dir_var.get()
        output_dir = self.output_dir_var.get()
        
        if not input_dir or not output_dir:
            messagebox.showerror("Error", "Please select both input and output directories")
            return
        
        if not os.path.exists(input_dir):
            messagebox.showerror("Error", f"Input directory does not exist: {input_dir}")
            return
        
        # Disable start button, enable stop button
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.resume_btn.config(state=tk.DISABLED)
        
        self.log("="*60)
        self.log("Starting batch processing...")
        self.log(f"Input:  {input_dir}")
        self.log(f"Output: {output_dir}")
        self.log("="*60)
        
        # Run in thread
        self.current_thread = threading.Thread(
            target=self._run_processing,
            args=(input_dir, output_dir, None)
        )
        self.current_thread.start()
    
    def resume_processing(self):
        """Resume from checkpoint."""
        checkpoints = self.processor.checkpoint_mgr.list_checkpoints()
        
        if not checkpoints:
            messagebox.showinfo("No Checkpoints", "No checkpoints available to resume")
            return
        
        # For simplicity, resume the most recent checkpoint
        job_id = checkpoints[-1]
        checkpoint = self.processor.checkpoint_mgr.load_checkpoint(job_id)
        
        if not checkpoint:
            messagebox.showerror("Error", "Failed to load checkpoint")
            return
        
        input_dir = checkpoint['input_dir']
        output_dir = checkpoint['output_dir']
        
        # Set directories
        self.input_dir_var.set(input_dir)
        self.output_dir_var.set(output_dir)
        
        # Disable buttons
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.resume_btn.config(state=tk.DISABLED)
        
        self.log("="*60)
        self.log(f"Resuming job: {job_id}")
        self.log(f"Previous progress: {checkpoint['processed_count']} of {checkpoint['total_files']}")
        self.log("="*60)
        
        # Run in thread
        self.current_thread = threading.Thread(
            target=self._run_processing,
            args=(input_dir, output_dir, job_id)
        )
        self.current_thread.start()
    
    def _run_processing(self, input_dir: str, output_dir: str, resume_job_id: Optional[str]):
        """Run processing in background thread."""
        try:
            result = self.processor.process_batch(
                input_dir, 
                output_dir, 
                resume_job_id,
                progress_callback=self.update_progress
            )
            
            # Update UI on main thread
            self.root.after(0, self._processing_complete, result)
            
        except Exception as e:
            self.root.after(0, self._processing_error, str(e))
    
    def _processing_complete(self, result: dict):
        """Handle processing completion."""
        self.log("="*60)
        self.log(f"Processing {result['status'].upper()}")
        self.log(f"Total files:  {result['total']}")
        self.log(f"Processed:    {result['processed']}")
        self.log(f"Failed:       {result['failed']}")
        self.log(f"Skipped:      {result['skipped']}")
        
        if result.get('checkpoint_saved'):
            self.log("Checkpoint saved for resume")
        
        self.log("="*60)
        
        # Re-enable buttons
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.check_for_checkpoints()
        
        # Show completion message
        if result['status'] == 'completed':
            messagebox.showinfo("Complete", 
                              f"Processing complete!\n"
                              f"Processed: {result['processed']} files\n"
                              f"Failed: {result['failed']} files")
            self.status_var.set("Complete")
        elif result['status'] == 'interrupted':
            messagebox.showinfo("Interrupted", 
                              "Processing stopped. You can resume from the checkpoint later.")
            self.status_var.set("Interrupted - can resume")
    
    def _processing_error(self, error: str):
        """Handle processing error."""
        self.log(f"[ERROR] {error}")
        messagebox.showerror("Error", f"Processing failed: {error}")
        
        # Re-enable buttons
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.check_for_checkpoints()
    
    def stop_processing(self):
        """Stop processing gracefully."""
        if messagebox.askyesno("Confirm Stop", 
                              "Are you sure you want to stop? Progress will be saved."):
            self.log("Stopping gracefully... please wait")
            self.processor.stop()
            self.stop_btn.config(state=tk.DISABLED)
    
    def run(self):
        """Run the GUI."""
        self.root.mainloop()

def main():
    """Main entry point."""
    app = MathTranslationGUI()
    app.run()

if __name__ == '__main__':
    main()
