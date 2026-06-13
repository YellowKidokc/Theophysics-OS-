"""
TTS Batch Processor for Theophysics - ENHANCED with Media Vault Transfer
==========================================================================
Walks an entire folder tree and processes all .md/.txt files through the TTS pipeline,
then automatically transfers completed audio files to the Media Vault with vault structure.

Usage:
    python batch_tts.py                    # Process INBOX, output to OUTBOX, transfer to Media
    python batch_tts.py --input "C:\\MyFolder" --output "C:\\AudioOutput"
    python batch_tts.py --flat             # Flatten output (no subfolders)
    python batch_tts.py --no-transfer      # Skip auto-transfer to media vault

Features:
    - Recursive folder processing
    - Preserves folder structure in output (or flatten with --flat)
    - Skips already-processed files (checks PROCESSED folder)
    - Uses Edge TTS by default (free)
    - Moves processed source files to PROCESSED folder
    - AUTO-TRANSFERS audio to O:\\00_MEDIA\\Audio replicating vault structure

Author: David Lowe / Theophysics Project
"""

import os
import sys
import asyncio
import shutil
import argparse
from pathlib import Path
from datetime import datetime

# Import the main pipeline
from tts_pipeline import TTSPipeline


class BatchTTSProcessor:
    """
    Batch processor that walks folders and processes all text files,
    then transfers to media vault.
    """
    
    def __init__(self,
                 input_dir: str = None,
                 output_dir: str = None,
                 processed_dir: str = None,
                 media_vault_dir: str = None,
                 publish_dir: str = None,
                 engine: str = 'edge',
                 voice: str = None,
                 prelude: str = None,
                 name_replacements: dict = None,
                 flatten: bool = False,
                 save_normalized: bool = True,
                 auto_transfer: bool = True,
                 auto_publish: bool = True):
        
        # Default directories relative to script location
        script_dir = Path(__file__).parent
        base_dir = script_dir.parent
        self.input_dir = Path(input_dir) if input_dir else base_dir / "INBOX"
        self.output_dir = Path(output_dir) if output_dir else base_dir / "OUTBOX"
        self.processed_dir = Path(processed_dir) if processed_dir else base_dir / "PROCESSED"
        
        # Media vault for final audio files (replicates vault structure)
        self.media_vault_dir = Path(media_vault_dir) if media_vault_dir else Path("O:/00_MEDIA/Audio")
        self.publish_dir = Path(publish_dir) if publish_dir else base_dir / "SUBSTACK_READY" / "Audio"
        
        self.engine = engine
        self.voice = voice
        self.prelude = prelude
        self.name_replacements = name_replacements or {}
        self.flatten = flatten
        self.save_normalized = save_normalized
        self.auto_transfer = auto_transfer
        self.auto_publish = auto_publish
        
        # Supported extensions
        self.extensions = {'.md', '.txt'}
        
        # Stats
        self.stats = {
            'processed': 0,
            'skipped': 0,
            'failed': 0,
            'transferred': 0,
            'published': 0,
            'total_files': 0
        }
        
        # Initialize pipeline
        self.pipeline = TTSPipeline(
            engine=engine,
            voice=voice,
            prelude=self.prelude,
            name_replacements=self.name_replacements
        )
    
    def discover_files(self) -> list:
        """Find all processable files in input directory."""
        files = []
        
        for root, dirs, filenames in os.walk(self.input_dir):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            
            for filename in filenames:
                if Path(filename).suffix.lower() in self.extensions:
                    full_path = Path(root) / filename
                    rel_path = full_path.relative_to(self.input_dir)
                    files.append({
                        'input': full_path,
                        'relative': rel_path,
                        'name': Path(filename).stem
                    })
        
        return files
    
    def get_output_path(self, file_info: dict) -> Path:
        """Determine output path for a file."""
        if self.flatten:
            # All outputs in root of output dir
            return self.output_dir / f"{file_info['name']}.mp3"
        else:
            # Preserve folder structure
            rel_dir = file_info['relative'].parent
            output_subdir = self.output_dir / rel_dir
            output_subdir.mkdir(parents=True, exist_ok=True)
            return output_subdir / f"{file_info['name']}.mp3"
    
    def get_processed_path(self, file_info: dict) -> Path:
        """Determine where to move processed source files."""
        if self.flatten:
            return self.processed_dir / file_info['relative'].name
        else:
            rel_dir = file_info['relative'].parent
            proc_subdir = self.processed_dir / rel_dir
            proc_subdir.mkdir(parents=True, exist_ok=True)
            return proc_subdir / file_info['relative'].name
    
    def get_media_vault_path(self, file_info: dict) -> Path:
        """Determine where to copy audio in media vault (replicates vault structure)."""
        rel_dir = file_info['relative'].parent
        media_subdir = self.media_vault_dir / rel_dir
        media_subdir.mkdir(parents=True, exist_ok=True)
        return media_subdir / f"{file_info['name']}.mp3"
    
    def is_already_processed(self, file_info: dict) -> bool:
        """Check if this file was already processed."""
        processed_path = self.get_processed_path(file_info)
        output_path = self.get_output_path(file_info)
        return processed_path.exists() or output_path.exists()
    
    async def process_file(self, file_info: dict) -> bool:
        """Process a single file through the enhanced pipeline (title-named outputs)."""
        input_path = str(file_info['input'])
        output_path = str(self.get_output_path(file_info))

        try:
            success, title = await self.pipeline.process(
                input_path,
                output_path,
                save_normalized=self.save_normalized,
                save_tts_txt=True,
                save_clean_md=True,
            )

            if success:
                # Move source to processed folder (keyed by original filename)
                processed_path = self.get_processed_path(file_info)
                shutil.move(input_path, processed_path)
                print(f"  [MOVED] Source -> {processed_path.name}")

            return success

        except Exception as e:
            print(f"  [ERROR] {e}")
            return False
    
    def transfer_to_media_vault(self):
        """
        Transfer all MP3 files from OUTBOX to Media Vault, replicating folder structure.
        Only transfers .mp3 files, leaves normalized .txt files in OUTBOX.
        """
        if not self.auto_transfer:
            return
        
        print("\n" + "=" * 60)
        print("TRANSFERRING TO MEDIA VAULT")
        print("=" * 60)
        print(f"Source:      {self.output_dir}")
        print(f"Destination: {self.media_vault_dir}")
        if self.auto_publish:
            print(f"Publish:     {self.publish_dir}")
        print("-" * 60)

        transferred_count = 0
        published_count = 0
        
        # Walk through OUTBOX and find all MP3 files
        for root, dirs, files in os.walk(self.output_dir):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            
            for filename in files:
                if filename.lower().endswith('.mp3'):
                    source_path = Path(root) / filename
                    
                    # Calculate relative path from OUTBOX
                    rel_path = source_path.relative_to(self.output_dir)
                    
                    # Determine destination in media vault
                    dest_path = self.media_vault_dir / rel_path
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Copy file
                    try:
                        shutil.copy2(source_path, dest_path)
                        print(f"  [COPIED] {rel_path}")
                        transferred_count += 1
                        if self.auto_publish:
                            publish_path = self.publish_dir / rel_path
                            publish_path.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(source_path, publish_path)
                            print(f"  [PUBLISH] {rel_path}")
                            published_count += 1
                    except Exception as e:
                        print(f"  [ERROR] Failed to copy {rel_path}: {e}")

        self.stats['transferred'] = transferred_count
        self.stats['published'] = published_count
        print("-" * 60)
        print(f"Total transferred: {transferred_count} files")
        if self.auto_publish:
            print(f"Total published:   {published_count} files")
        print("=" * 60)
    
    async def run(self):
        """Main batch processing loop."""
        print("=" * 60)
        print("THEOPHYSICS TTS BATCH PROCESSOR")
        print("=" * 60)
        print(f"Input:       {self.input_dir}")
        print(f"Output:      {self.output_dir}")
        print(f"Processed:   {self.processed_dir}")
        print(f"Media Vault: {self.media_vault_dir}")
        if self.auto_publish:
            print(f"Publish Dir: {self.publish_dir}")
        print(f"Engine:      {self.engine.upper()}")
        print(f"Voice:       {self.voice or 'default'}")
        print(f"Flatten:     {self.flatten}")
        print(f"Auto-Transfer: {self.auto_transfer}")
        print(f"Auto-Publish:  {self.auto_publish}")
        print("=" * 60)
        
        # Ensure directories exist
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.media_vault_dir.mkdir(parents=True, exist_ok=True)
        if self.auto_publish:
            self.publish_dir.mkdir(parents=True, exist_ok=True)
        
        # Discover files
        print("\n[SCANNING] Looking for files...")
        files = self.discover_files()
        self.stats['total_files'] = len(files)
        
        if not files:
            print("[INFO] No files found to process.")
            # Still run transfer in case there are files in OUTBOX from previous runs
            if self.auto_transfer:
                self.transfer_to_media_vault()
            return
        
        print(f"[FOUND] {len(files)} file(s) to process\n")
        
        # Process each file
        for i, file_info in enumerate(files, 1):
            print(f"\n[{i}/{len(files)}] {file_info['relative']}")
            
            if self.is_already_processed(file_info):
                print("  [SKIP] Already processed")
                self.stats['skipped'] += 1
                continue
            
            success = await self.process_file(file_info)
            
            if success:
                self.stats['processed'] += 1
            else:
                self.stats['failed'] += 1
        
        # Transfer to media vault
        if self.auto_transfer:
            self.transfer_to_media_vault()
        
        # Summary
        print("\n" + "=" * 60)
        print("BATCH COMPLETE")
        print("=" * 60)
        print(f"Total files:  {self.stats['total_files']}")
        print(f"Processed:    {self.stats['processed']}")
        print(f"Skipped:      {self.stats['skipped']}")
        print(f"Failed:       {self.stats['failed']}")
        if self.auto_transfer:
            print(f"Transferred:  {self.stats['transferred']}")
            if self.auto_publish:
                print(f"Published:    {self.stats['published']}")
        print("=" * 60)


async def main():
    parser = argparse.ArgumentParser(
        description='Batch TTS Processor for Theophysics with Media Vault Transfer',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python batch_tts.py                           # Process INBOX, output to OUTBOX, transfer to Media
  python batch_tts.py --input "D:\\Papers"      # Process custom folder
  python batch_tts.py --flat                    # Flatten output structure
  python batch_tts.py --no-transfer             # Skip media vault transfer
  python batch_tts.py --engine openai           # Use OpenAI TTS (costs $$$)
  python batch_tts.py --media "D:\\MyMedia"     # Custom media vault location
        """
    )
    
    parser.add_argument('--input', '-i', help='Input directory (default: INBOX)')
    parser.add_argument('--output', '-o', help='Output directory (default: OUTBOX)')
    parser.add_argument('--processed', '-p', help='Processed files directory (default: PROCESSED)')
    parser.add_argument('--media', '-m', help='Media vault directory (default: O:/00_MEDIA/Audio)')
    parser.add_argument('--publish', help='Publish-ready mirror directory (default: ../SUBSTACK_READY/Audio)')
    parser.add_argument('--engine', '-e', choices=['edge', 'openai'], default='edge',
                       help='TTS engine (default: edge = FREE)')
    parser.add_argument('--voice', '-v', help='Voice name')
    parser.add_argument('--flat', '-f', action='store_true',
                       help='Flatten output (no subfolders)')
    parser.add_argument('--no-transfer', action='store_true',
                       help='Skip auto-transfer to media vault')
    parser.add_argument('--no-publish', action='store_true',
                       help='Skip publish-ready mirror copy')
    parser.add_argument('--no-normalized', action='store_true',
                       help='Do not save normalized text files')
    parser.add_argument('--prelude', default='Faith Through Physics. Theophysics Vault. By David Lowe',
                       help='Optional spoken prelude prepended to each TTS file')
    parser.add_argument('--replace-name', action='append', default=[],
                       help='Name replacement pair SOURCE=TARGET (repeatable)')
    
    args = parser.parse_args()
    
    replacements = {}
    for pair in args.replace_name:
        if "=" not in pair:
            print(f"[WARNING] Skipping invalid --replace-name '{pair}' (expected SOURCE=TARGET)")
            continue
        src, dst = pair.split("=", 1)
        src = src.strip()
        dst = dst.strip()
        if src:
            replacements[src] = dst

    processor = BatchTTSProcessor(
        input_dir=args.input,
        output_dir=args.output,
        processed_dir=args.processed,
        media_vault_dir=args.media,
        publish_dir=args.publish,
        engine=args.engine,
        voice=args.voice,
        prelude=args.prelude,
        name_replacements=replacements,
        flatten=args.flat,
        auto_transfer=not args.no_transfer,
        auto_publish=not args.no_publish,
        save_normalized=not args.no_normalized
    )
    
    await processor.run()


if __name__ == '__main__':
    asyncio.run(main())
