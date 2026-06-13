"""
Quick Transfer Utility - Move existing OUTBOX files to Media Vault
===================================================================
Use this if you want to transfer files that are already in OUTBOX
without re-processing them.

Usage:
    python transfer_existing.py
"""

import os
import shutil
from pathlib import Path

def transfer_outbox_to_media():
    """Transfer all MP3 files from OUTBOX to Media Vault."""
    
    outbox = Path("O:/Theophysics_Backend/TTS_Pipeline/OUTBOX")
    media_vault = Path("O:/00_MEDIA/Audio")
    
    print("=" * 70)
    print("TRANSFER EXISTING OUTBOX FILES TO MEDIA VAULT")
    print("=" * 70)
    print(f"Source:      {outbox}")
    print(f"Destination: {media_vault}")
    print("-" * 70)
    
    if not outbox.exists():
        print("[ERROR] OUTBOX not found!")
        return
    
    media_vault.mkdir(parents=True, exist_ok=True)
    
    transferred = 0
    skipped = 0
    
    # Walk through OUTBOX
    for root, dirs, files in os.walk(outbox):
        # Skip hidden directories
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        
        for filename in files:
            if filename.lower().endswith('.mp3'):
                source_path = Path(root) / filename
                rel_path = source_path.relative_to(outbox)
                dest_path = media_vault / rel_path
                
                # Create destination directory
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Check if already exists
                if dest_path.exists():
                    print(f"  [SKIP] {rel_path} (already exists)")
                    skipped += 1
                else:
                    try:
                        shutil.copy2(source_path, dest_path)
                        print(f"  [COPIED] {rel_path}")
                        transferred += 1
                    except Exception as e:
                        print(f"  [ERROR] {rel_path}: {e}")
    
    print("-" * 70)
    print(f"Transferred: {transferred} files")
    print(f"Skipped:     {skipped} files (already existed)")
    print("=" * 70)

if __name__ == '__main__':
    transfer_outbox_to_media()
    input("\nPress Enter to exit...")
