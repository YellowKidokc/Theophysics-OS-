"""
TTS + Google Drive Upload Pipeline with Checkpoint/Resume
==========================================================
Combines TTS processing with automatic Google Drive upload.
Handles interruptions gracefully with checkpoint system.

Usage:
    python tts_and_upload.py                    # Full pipeline: TTS + Upload
    python tts_and_upload.py --tts-only         # Just TTS, no upload
    python tts_and_upload.py --upload-only      # Just upload existing audio
    python tts_and_upload.py --resume           # Resume from last checkpoint
    python tts_and_upload.py --status           # Show current progress

Author: Theophysics Project
"""

import os
import sys
import json
import time
import signal
import atexit
from pathlib import Path
from datetime import datetime

# ============================================================================
# CONFIGURATION
# ============================================================================

CONFIG = {
    # Directories
    'inbox': 'O:/Theophysics_Backend/TTS_Engines/TTS_Pipeline/INBOX',
    'outbox': 'O:/Theophysics_Backend/TTS_Engines/TTS_Pipeline/OUTBOX',
    'processed': 'O:/Theophysics_Backend/TTS_Engines/TTS_Pipeline/PROCESSED',
    'audio_output': 'O:/00_MEDIA/Audio',

    # Checkpoint file
    'checkpoint_file': 'O:/Theophysics_Backend/TTS_Engines/TTS_Pipeline/.pipeline_checkpoint.json',

    # Google Drive settings
    'gdrive_credentials': 'O:/Theophysics_Data/google-drive-credentials.json',
    'gdrive_folder_id': '1Wpj3KM5-tzkCk1zfOg4MVuRbzjMw83aZ',
    'link_map_file': 'O:/Theophysics_Data/audio_link_map.json',

    # Papers location (for link insertion)
    'papers_dir': 'O:/_THEO/THEO/TM SUBSTACK/TM SUBSTACK/03_PUBLICATIONS',
}

# ============================================================================
# CHECKPOINT MANAGER
# ============================================================================

class CheckpointManager:
    """Manages pipeline state for graceful resume after interruption."""

    def __init__(self, checkpoint_file: str):
        self.checkpoint_file = Path(checkpoint_file)
        self.state = self._load()
        self._shutdown_requested = False

        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        atexit.register(self._save)

    def _load(self) -> dict:
        """Load checkpoint state from file."""
        if self.checkpoint_file.exists():
            try:
                with open(self.checkpoint_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {
            'phase': 'idle',           # idle, tts, upload, complete
            'tts_completed': [],       # Files that have been TTS'd
            'upload_completed': [],    # Files that have been uploaded
            'current_file': None,      # Currently processing
            'started': None,
            'last_update': None,
            'total_files': 0,
            'errors': []
        }

    def _save(self):
        """Save checkpoint state to file."""
        self.state['last_update'] = datetime.now().isoformat()
        self.checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.checkpoint_file, 'w') as f:
            json.dump(self.state, f, indent=2)

    def _handle_shutdown(self, signum, frame):
        """Handle shutdown signal gracefully."""
        print("\n\n⚠️  Shutdown requested - saving checkpoint...")
        self._shutdown_requested = True
        self._save()
        print(f"✓ Checkpoint saved. Run with --resume to continue.")
        sys.exit(0)

    @property
    def shutdown_requested(self) -> bool:
        return self._shutdown_requested

    def start_session(self, total_files: int):
        """Start a new processing session."""
        self.state['started'] = datetime.now().isoformat()
        self.state['total_files'] = total_files
        self._save()

    def set_phase(self, phase: str):
        """Set current phase."""
        self.state['phase'] = phase
        self._save()

    def start_file(self, filename: str):
        """Mark file as currently processing."""
        self.state['current_file'] = filename
        self._save()

    def complete_tts(self, filename: str):
        """Mark file as TTS complete."""
        if filename not in self.state['tts_completed']:
            self.state['tts_completed'].append(filename)
        self.state['current_file'] = None
        self._save()

    def complete_upload(self, filename: str):
        """Mark file as upload complete."""
        if filename not in self.state['upload_completed']:
            self.state['upload_completed'].append(filename)
        self._save()

    def add_error(self, filename: str, error: str):
        """Record an error."""
        self.state['errors'].append({
            'file': filename,
            'error': error,
            'time': datetime.now().isoformat()
        })
        self._save()

    def is_tts_complete(self, filename: str) -> bool:
        """Check if file has been TTS'd."""
        return filename in self.state['tts_completed']

    def is_uploaded(self, filename: str) -> bool:
        """Check if file has been uploaded."""
        return filename in self.state['upload_completed']

    def clear(self):
        """Clear checkpoint (start fresh)."""
        self.state = {
            'phase': 'idle',
            'tts_completed': [],
            'upload_completed': [],
            'current_file': None,
            'started': None,
            'last_update': None,
            'total_files': 0,
            'errors': []
        }
        self._save()

    def get_status(self) -> str:
        """Get human-readable status."""
        lines = [
            "=" * 50,
            "PIPELINE STATUS",
            "=" * 50,
            f"Phase: {self.state['phase']}",
            f"Started: {self.state.get('started', 'N/A')}",
            f"Last Update: {self.state.get('last_update', 'N/A')}",
            f"Total Files: {self.state['total_files']}",
            f"TTS Complete: {len(self.state['tts_completed'])}",
            f"Upload Complete: {len(self.state['upload_completed'])}",
            f"Current File: {self.state.get('current_file', 'None')}",
            f"Errors: {len(self.state['errors'])}",
        ]
        if self.state['errors']:
            lines.append("\nRecent Errors:")
            for err in self.state['errors'][-5:]:
                lines.append(f"  - {err['file']}: {err['error']}")
        return "\n".join(lines)


# ============================================================================
# TTS PROCESSOR (wraps existing batch_tts.py)
# ============================================================================

class TTSProcessor:
    """Wrapper for existing TTS pipeline with checkpoint support."""

    def __init__(self, checkpoint: CheckpointManager):
        self.checkpoint = checkpoint

        # Import existing pipeline
        try:
            from batch_tts import BatchTTSProcessor
            self.processor = BatchTTSProcessor(auto_transfer=True)
        except ImportError:
            print("ERROR: Could not import batch_tts.py")
            sys.exit(1)

    def process_files(self, files: list) -> int:
        """Process files through TTS, respecting checkpoints."""
        self.checkpoint.set_phase('tts')
        processed = 0

        for file_info in files:
            if self.checkpoint.shutdown_requested:
                break

            filename = file_info['name']

            # Skip if already done
            if self.checkpoint.is_tts_complete(filename):
                print(f"  ⏭ Skipping (already done): {filename}")
                continue

            self.checkpoint.start_file(filename)
            print(f"\n  🔊 Processing TTS: {filename}")

            try:
                # Process single file
                self.processor.process_file(file_info)
                self.checkpoint.complete_tts(filename)
                processed += 1
                print(f"  ✓ TTS complete: {filename}")
            except Exception as e:
                self.checkpoint.add_error(filename, str(e))
                print(f"  ✗ Error: {e}")

        return processed


# ============================================================================
# GOOGLE DRIVE UPLOADER
# ============================================================================

class DriveUploader:
    """Uploads audio files to Google Drive with checkpoint support."""

    def __init__(self, checkpoint: CheckpointManager, credentials_file: str, folder_id: str):
        self.checkpoint = checkpoint
        self.folder_id = folder_id
        self.link_map = {}
        self.service = None

        if folder_id != 'YOUR_FOLDER_ID_HERE':
            self._init_service(credentials_file)

    def _init_service(self, credentials_file: str):
        """Initialize Google Drive API."""
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload

            self.MediaFileUpload = MediaFileUpload
            credentials = service_account.Credentials.from_service_account_file(
                credentials_file,
                scopes=['https://www.googleapis.com/auth/drive.file']
            )
            self.service = build('drive', 'v3', credentials=credentials)
            print("✓ Google Drive API initialized")
        except ImportError:
            print("⚠️ Google API not installed. Run: pip install google-auth google-api-python-client")
            self.service = None
        except Exception as e:
            print(f"⚠️ Google Drive init error: {e}")
            self.service = None

    def upload_files(self, audio_dir: str) -> int:
        """Upload audio files to Google Drive."""
        if not self.service:
            print("⚠️ Google Drive not configured - skipping upload")
            return 0

        self.checkpoint.set_phase('upload')
        audio_path = Path(audio_dir)
        uploaded = 0

        for audio_file in audio_path.rglob('*.mp3'):
            if self.checkpoint.shutdown_requested:
                break

            filename = audio_file.name

            # Skip if already uploaded
            if self.checkpoint.is_uploaded(filename):
                print(f"  ⏭ Skipping (already uploaded): {filename}")
                continue

            print(f"\n  ☁️ Uploading: {filename}")

            try:
                file_info = self._upload_file(audio_file)
                self.checkpoint.complete_upload(filename)
                self.link_map[filename] = file_info
                uploaded += 1
                print(f"  ✓ Uploaded: {filename}")
                print(f"    Link: {file_info.get('webViewLink', 'N/A')}")
            except Exception as e:
                self.checkpoint.add_error(filename, str(e))
                print(f"  ✗ Upload error: {e}")

        # Save link map
        self._save_link_map()
        return uploaded

    def _upload_file(self, local_path: Path) -> dict:
        """Upload single file and return file info."""
        file_metadata = {
            'name': local_path.name,
            'parents': [self.folder_id]
        }

        media = self.MediaFileUpload(
            str(local_path),
            mimetype='audio/mpeg',
            resumable=True
        )

        file = self.service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, name, webViewLink, webContentLink'
        ).execute()

        # Make shareable
        self.service.permissions().create(
            fileId=file['id'],
            body={'type': 'anyone', 'role': 'reader'}
        ).execute()

        return file

    def _save_link_map(self):
        """Save link map to file."""
        link_map_file = Path(CONFIG['link_map_file'])

        # Load existing
        existing = {}
        if link_map_file.exists():
            with open(link_map_file, 'r') as f:
                existing = json.load(f)

        # Merge
        for filename, info in self.link_map.items():
            existing[filename] = {
                'id': info.get('id'),
                'view_link': info.get('webViewLink'),
                'download_link': info.get('webContentLink'),
                'uploaded': datetime.now().isoformat()
            }

        # Save
        link_map_file.parent.mkdir(parents=True, exist_ok=True)
        with open(link_map_file, 'w') as f:
            json.dump(existing, f, indent=2)

        print(f"\n✓ Link map saved: {link_map_file}")


# ============================================================================
# MAIN PIPELINE
# ============================================================================

def run_pipeline(tts_only: bool = False, upload_only: bool = False, resume: bool = False):
    """Run the full pipeline."""

    print("=" * 60)
    print("TTS + UPLOAD PIPELINE")
    print("=" * 60)

    checkpoint = CheckpointManager(CONFIG['checkpoint_file'])

    if not resume:
        checkpoint.clear()

    # Discover files
    inbox = Path(CONFIG['inbox'])
    files = []
    for ext in ['.md', '.txt']:
        files.extend([{'name': f.stem, 'path': f} for f in inbox.rglob(f'*{ext}')])

    print(f"\nFound {len(files)} files to process")
    checkpoint.start_session(len(files))

    # Phase 1: TTS
    if not upload_only:
        print("\n--- PHASE 1: TEXT-TO-SPEECH ---")
        tts = TTSProcessor(checkpoint)
        tts_count = tts.process_files(files)
        print(f"\n✓ TTS processed: {tts_count} files")

        if checkpoint.shutdown_requested:
            return

    # Phase 2: Upload
    if not tts_only:
        print("\n--- PHASE 2: GOOGLE DRIVE UPLOAD ---")
        uploader = DriveUploader(
            checkpoint,
            CONFIG['gdrive_credentials'],
            CONFIG['gdrive_folder_id']
        )
        upload_count = uploader.upload_files(CONFIG['audio_output'])
        print(f"\n✓ Uploaded: {upload_count} files")

    checkpoint.set_phase('complete')
    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE!")
    print("=" * 60)
    print(checkpoint.get_status())


# ============================================================================
# CLI
# ============================================================================

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='TTS + Google Drive Upload Pipeline')
    parser.add_argument('--tts-only', action='store_true', help='Only run TTS, skip upload')
    parser.add_argument('--upload-only', action='store_true', help='Only upload, skip TTS')
    parser.add_argument('--resume', action='store_true', help='Resume from last checkpoint')
    parser.add_argument('--status', action='store_true', help='Show pipeline status')
    parser.add_argument('--clear', action='store_true', help='Clear checkpoint and start fresh')

    args = parser.parse_args()

    if args.status:
        checkpoint = CheckpointManager(CONFIG['checkpoint_file'])
        print(checkpoint.get_status())
    elif args.clear:
        checkpoint = CheckpointManager(CONFIG['checkpoint_file'])
        checkpoint.clear()
        print("✓ Checkpoint cleared")
    else:
        run_pipeline(
            tts_only=args.tts_only,
            upload_only=args.upload_only,
            resume=args.resume
        )
