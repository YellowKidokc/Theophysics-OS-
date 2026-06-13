"""
Bundle TTS Outputs for Google Drive
====================================
Organizes processed files into structured folders for Drive sync.

Creates:
- TTS_Audio/           → All MP3 files
- TTS_Transcripts/     → All normalized text files (math translated)

Usage:
    python bundle_for_drive.py                    # Bundle and upload
    python bundle_for_drive.py --bundle-only      # Just organize locally
    python bundle_for_drive.py --get-links        # Get links for existing files

Author: Theophysics Project
"""

import os
import sys
import shutil
import json
from pathlib import Path
from datetime import datetime

# ============================================================================
# CONFIGURATION
# ============================================================================

CONFIG = {
    # Source directories
    'outbox': 'O:/Theophysics_Backend/TTS_Engines/TTS_Pipeline/OUTBOX',
    'media_vault': 'O:/00_MEDIA/Audio',

    # Bundle output (this should be in a GoodSync-synced folder)
    'bundle_root': 'O:/Theophysics_Data/Theophysics_Moral_Decay_of_America/TTS_Bundle',

    # Google Drive settings
    'gdrive_credentials': 'O:/Theophysics_Data/google-drive-credentials.json',
    'gdrive_folder_id': '1Wpj3KM5-tzkCk1zfOg4MVuRbzjMw83aZ',
    'link_map_file': 'O:/Theophysics_Data/audio_link_map.json',
}

# ============================================================================
# BUNDLER
# ============================================================================

class TTSBundler:
    """Organizes TTS output files into structured folders."""

    def __init__(self, config: dict):
        self.config = config
        self.bundle_root = Path(config['bundle_root'])
        self.audio_dir = self.bundle_root / 'TTS_Audio'
        self.transcript_dir = self.bundle_root / 'TTS_Transcripts'
        self.stats = {'audio': 0, 'transcripts': 0, 'skipped': 0}

    def setup_folders(self):
        """Create bundle folder structure."""
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        self.transcript_dir.mkdir(parents=True, exist_ok=True)
        print(f"✓ Bundle folders ready at: {self.bundle_root}")

    def bundle_from_outbox(self):
        """Copy files from OUTBOX to bundle folders."""
        outbox = Path(self.config['outbox'])

        if not outbox.exists():
            print(f"ERROR: OUTBOX not found: {outbox}")
            return

        print(f"\nScanning: {outbox}")

        for file in outbox.rglob('*'):
            if file.is_dir():
                continue

            if file.suffix.lower() == '.mp3':
                self._copy_file(file, self.audio_dir / file.name, 'audio')
            elif file.name.endswith('_normalized.txt'):
                self._copy_file(file, self.transcript_dir / file.name, 'transcripts')

    def bundle_from_media_vault(self):
        """Copy files from Media Vault to bundle folders."""
        media_vault = Path(self.config['media_vault'])

        if not media_vault.exists():
            print(f"⚠️ Media vault not found: {media_vault}")
            return

        print(f"\nScanning: {media_vault}")

        for file in media_vault.rglob('*.mp3'):
            self._copy_file(file, self.audio_dir / file.name, 'audio')

    def _copy_file(self, src: Path, dst: Path, category: str):
        """Copy file if it doesn't exist or is newer."""
        if dst.exists():
            # Check if source is newer
            if src.stat().st_mtime <= dst.stat().st_mtime:
                self.stats['skipped'] += 1
                return

        print(f"  → {category}: {src.name}")
        shutil.copy2(src, dst)
        self.stats[category] += 1

    def create_index(self):
        """Create an index file listing all bundled files."""
        index_file = self.bundle_root / 'INDEX.md'

        lines = [
            "# TTS Bundle Index",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "## Audio Files",
            ""
        ]

        for f in sorted(self.audio_dir.glob('*.mp3')):
            lines.append(f"- [{f.stem}](TTS_Audio/{f.name})")

        lines.extend([
            "",
            "## Transcripts (Math-Translated)",
            ""
        ])

        for f in sorted(self.transcript_dir.glob('*.txt')):
            lines.append(f"- [{f.stem}](TTS_Transcripts/{f.name})")

        with open(index_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        print(f"\n✓ Index created: {index_file}")

    def get_summary(self) -> str:
        """Return bundle summary."""
        return f"""
Bundle Complete!
================
Location: {self.bundle_root}

Audio files:      {self.stats['audio']} copied
Transcripts:      {self.stats['transcripts']} copied
Skipped (same):   {self.stats['skipped']}

Folders:
  - TTS_Audio/       ({len(list(self.audio_dir.glob('*.mp3')))} files)
  - TTS_Transcripts/ ({len(list(self.transcript_dir.glob('*.txt')))} files)
"""


# ============================================================================
# GOOGLE DRIVE LINK GETTER
# ============================================================================

class DriveLinkGetter:
    """Gets shareable links for files already in Google Drive."""

    def __init__(self, credentials_file: str, folder_id: str):
        self.folder_id = folder_id
        self.service = None
        self._init_service(credentials_file)

    def _init_service(self, credentials_file: str):
        """Initialize Google Drive API."""
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build

            credentials = service_account.Credentials.from_service_account_file(
                credentials_file,
                scopes=['https://www.googleapis.com/auth/drive']
            )
            self.service = build('drive', 'v3', credentials=credentials)
            print("✓ Google Drive API connected")
        except ImportError:
            print("⚠️ Google API not installed. Run: pip install google-auth google-api-python-client")
        except Exception as e:
            print(f"⚠️ Google Drive error: {e}")

    def get_all_files(self) -> list:
        """Get all files in the Drive folder (recursive)."""
        if not self.service:
            return []

        files = []
        page_token = None

        while True:
            query = f"'{self.folder_id}' in parents or '{self.folder_id}' in parents"
            results = self.service.files().list(
                q=f"'{self.folder_id}' in parents",
                pageSize=100,
                fields="nextPageToken, files(id, name, mimeType, webViewLink, webContentLink)",
                pageToken=page_token
            ).execute()

            files.extend(results.get('files', []))
            page_token = results.get('nextPageToken')

            if not page_token:
                break

        # Also check subfolders
        folders = [f for f in files if f['mimeType'] == 'application/vnd.google-apps.folder']
        for folder in folders:
            subfiles = self._get_files_in_folder(folder['id'])
            files.extend(subfiles)

        return files

    def _get_files_in_folder(self, folder_id: str) -> list:
        """Get files in a specific folder."""
        files = []
        page_token = None

        while True:
            results = self.service.files().list(
                q=f"'{folder_id}' in parents",
                pageSize=100,
                fields="nextPageToken, files(id, name, mimeType, webViewLink, webContentLink)",
                pageToken=page_token
            ).execute()

            files.extend(results.get('files', []))
            page_token = results.get('nextPageToken')

            if not page_token:
                break

        return files

    def make_shareable(self, file_id: str):
        """Make a file shareable and return the link."""
        try:
            # Check if already shared
            permissions = self.service.permissions().list(fileId=file_id).execute()
            is_public = any(p.get('type') == 'anyone' for p in permissions.get('permissions', []))

            if not is_public:
                self.service.permissions().create(
                    fileId=file_id,
                    body={'type': 'anyone', 'role': 'reader'}
                ).execute()

            # Get updated file info
            file = self.service.files().get(
                fileId=file_id,
                fields='webViewLink, webContentLink'
            ).execute()

            return file.get('webViewLink')
        except Exception as e:
            print(f"  ⚠️ Error making shareable: {e}")
            return None

    def get_links_for_audio(self) -> dict:
        """Get shareable links for all audio files."""
        files = self.get_all_files()
        audio_files = [f for f in files if f['name'].endswith('.mp3')]

        print(f"\nFound {len(audio_files)} audio files in Drive")

        links = {}
        for f in audio_files:
            print(f"  Processing: {f['name']}")
            link = f.get('webViewLink')
            if not link:
                link = self.make_shareable(f['id'])
            if link:
                links[f['name']] = {
                    'id': f['id'],
                    'view_link': link,
                    'download_link': f.get('webContentLink')
                }

        return links

    def save_link_map(self, links: dict, output_file: str):
        """Save link map to JSON file."""
        # Load existing
        output_path = Path(output_file)
        existing = {}
        if output_path.exists():
            with open(output_path, 'r') as f:
                existing = json.load(f)

        # Merge
        existing.update(links)

        # Save
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(existing, f, indent=2)

        print(f"\n✓ Link map saved: {output_file}")
        print(f"  Total files mapped: {len(existing)}")


# ============================================================================
# MAIN
# ============================================================================

def main(bundle_only: bool = False, get_links: bool = False):
    """Run the bundling and link-getting pipeline."""

    print("=" * 60)
    print("TTS BUNDLE FOR GOOGLE DRIVE")
    print("=" * 60)

    # Step 1: Bundle files
    if not get_links:
        print("\n--- STEP 1: Bundle Files ---")
        bundler = TTSBundler(CONFIG)
        bundler.setup_folders()
        bundler.bundle_from_outbox()
        bundler.bundle_from_media_vault()
        bundler.create_index()
        print(bundler.get_summary())

    if bundle_only:
        print("\n✓ Bundle complete. GoodSync will sync to Drive.")
        print("  Run with --get-links after sync to get shareable links.")
        return

    # Step 2: Get Drive links
    print("\n--- STEP 2: Get Google Drive Links ---")

    if not Path(CONFIG['gdrive_credentials']).exists():
        print(f"⚠️ Credentials not found: {CONFIG['gdrive_credentials']}")
        print("  Please move your JSON key file there first.")
        return

    linker = DriveLinkGetter(
        CONFIG['gdrive_credentials'],
        CONFIG['gdrive_folder_id']
    )

    links = linker.get_links_for_audio()
    linker.save_link_map(links, CONFIG['link_map_file'])

    print("\n" + "=" * 60)
    print("COMPLETE!")
    print("=" * 60)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Bundle TTS outputs for Google Drive')
    parser.add_argument('--bundle-only', action='store_true', help='Just bundle, skip link getting')
    parser.add_argument('--get-links', action='store_true', help='Just get links for existing Drive files')

    args = parser.parse_args()

    main(bundle_only=args.bundle_only, get_links=args.get_links)
