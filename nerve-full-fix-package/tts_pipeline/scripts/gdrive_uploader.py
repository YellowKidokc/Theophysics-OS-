"""
Google Drive Uploader + Link Inserter for Theophysics TTS Pipeline
====================================================================
Uploads audio files to Google Drive and inserts shareable links into papers.

Setup Required:
    1. Create Google Cloud project
    2. Enable Google Drive API
    3. Create Service Account + download JSON key
    4. Share your Drive folder with the service account email
    5. Set GDRIVE_FOLDER_ID in config below

Usage:
    python gdrive_uploader.py                          # Upload all audio, update all papers
    python gdrive_uploader.py --upload-only            # Just upload, don't update papers
    python gdrive_uploader.py --dry-run                # Show what would happen, don't do it

Author: Theophysics Project
"""

import os
import sys
import json
import re
from pathlib import Path
from datetime import datetime

# ============================================================================
# CONFIGURATION - EDIT THESE
# ============================================================================

CONFIG = {
    # Path to your Google service account credentials JSON
    'credentials_file': 'O:/Theophysics_Data/google-drive-credentials.json',

    # Google Drive folder ID (from the folder URL)
    # Example: https://drive.google.com/drive/folders/1ABC123... → folder_id = "1ABC123..."
    'gdrive_folder_id': '1Wpj3KM5-tzkCk1zfOg4MVuRbzjMw83aZ',

    # Where your audio files are
    'audio_source_dir': 'O:/00_MEDIA/Audio',

    # Where your papers are (to insert links)
    'papers_dir': 'O:/_THEO/THEO/TM SUBSTACK/TM SUBSTACK/03_PUBLICATIONS',

    # Link mapping file (tracks audio → drive link)
    'link_map_file': 'O:/Theophysics_Data/audio_link_map.json',

    # Pattern to find audio references in papers (customize as needed)
    # This looks for: [Audio: filename.mp3] or similar patterns
    'audio_patterns': [
        r'\[Audio:\s*([^\]]+)\]',           # [Audio: filename.mp3]
        r'\[Listen:\s*([^\]]+)\]',          # [Listen: filename.mp3]
        r'%%audio\s+([^\s%]+)\s*%%',        # %%audio filename.mp3%%
        r'\{\{audio:\s*([^\}]+)\}\}',       # {{audio: filename.mp3}}
    ]
}

# ============================================================================
# GOOGLE DRIVE CLIENT
# ============================================================================

class GoogleDriveUploader:
    """Handles Google Drive uploads and link generation."""

    def __init__(self, credentials_file: str, folder_id: str):
        self.folder_id = folder_id
        self.service = None
        self._init_service(credentials_file)

    def _init_service(self, credentials_file: str):
        """Initialize Google Drive API service."""
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
            print(f"✓ Google Drive API initialized")

        except ImportError:
            print("ERROR: Google API libraries not installed.")
            print("Run: pip install google-auth google-auth-oauthlib google-api-python-client")
            sys.exit(1)
        except Exception as e:
            print(f"ERROR initializing Google Drive: {e}")
            sys.exit(1)

    def upload_file(self, local_path: str, filename: str = None) -> dict:
        """Upload a file and return file info with shareable link."""
        local_path = Path(local_path)
        filename = filename or local_path.name

        # Check if already exists in Drive
        existing = self._find_file(filename)
        if existing:
            print(f"  ⏭ Already exists: {filename}")
            return existing

        # Upload
        file_metadata = {
            'name': filename,
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

        # Get shareable link
        file = self.service.files().get(
            fileId=file['id'],
            fields='id, name, webViewLink, webContentLink'
        ).execute()

        print(f"  ✓ Uploaded: {filename}")
        return file

    def _find_file(self, filename: str) -> dict:
        """Check if file already exists in the folder."""
        query = f"name='{filename}' and '{self.folder_id}' in parents and trashed=false"
        results = self.service.files().list(
            q=query,
            fields='files(id, name, webViewLink, webContentLink)'
        ).execute()
        files = results.get('files', [])
        return files[0] if files else None


# ============================================================================
# LINK MAP MANAGER
# ============================================================================

class LinkMapManager:
    """Manages the audio filename → Google Drive link mapping."""

    def __init__(self, map_file: str):
        self.map_file = Path(map_file)
        self.links = self._load()

    def _load(self) -> dict:
        """Load existing link map."""
        if self.map_file.exists():
            with open(self.map_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def save(self):
        """Save link map to file."""
        self.map_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.map_file, 'w', encoding='utf-8') as f:
            json.dump(self.links, f, indent=2)
        print(f"✓ Link map saved: {self.map_file}")

    def add(self, filename: str, file_info: dict):
        """Add a file to the link map."""
        self.links[filename] = {
            'id': file_info.get('id'),
            'view_link': file_info.get('webViewLink'),
            'download_link': file_info.get('webContentLink'),
            'uploaded': datetime.now().isoformat()
        }

    def get_link(self, filename: str) -> str:
        """Get the shareable link for a filename."""
        if filename in self.links:
            return self.links[filename].get('view_link')
        return None


# ============================================================================
# PAPER UPDATER
# ============================================================================

class PaperUpdater:
    """Updates papers with Google Drive links."""

    def __init__(self, link_map: LinkMapManager, patterns: list):
        self.link_map = link_map
        self.patterns = [re.compile(p) for p in patterns]

    def update_file(self, file_path: Path, dry_run: bool = False) -> int:
        """Update a single file, replacing audio refs with links. Returns count of replacements."""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        original = content
        replacements = 0

        for pattern in self.patterns:
            def replace_match(match):
                nonlocal replacements
                audio_ref = match.group(1).strip()

                # Try to find link
                link = self.link_map.get_link(audio_ref)
                if not link:
                    # Try with .mp3 extension
                    link = self.link_map.get_link(audio_ref + '.mp3')
                if not link:
                    # Try without extension
                    base = Path(audio_ref).stem
                    link = self.link_map.get_link(base + '.mp3')

                if link:
                    replacements += 1
                    return f'[🎧 Listen]({link})'
                else:
                    return match.group(0)  # Keep original if no link found

            content = pattern.sub(replace_match, content)

        if replacements > 0 and not dry_run:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

        return replacements

    def update_folder(self, folder: Path, dry_run: bool = False) -> dict:
        """Update all papers in a folder. Returns stats."""
        stats = {'files_checked': 0, 'files_updated': 0, 'links_inserted': 0}

        extensions = {'.md', '.txt'}

        for root, dirs, files in os.walk(folder):
            # Skip hidden/system folders
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in {'node_modules', 'venv', '__pycache__'}]

            for filename in files:
                if Path(filename).suffix.lower() in extensions:
                    file_path = Path(root) / filename
                    stats['files_checked'] += 1

                    count = self.update_file(file_path, dry_run)
                    if count > 0:
                        stats['files_updated'] += 1
                        stats['links_inserted'] += count
                        action = "Would update" if dry_run else "Updated"
                        print(f"  {action}: {file_path.name} ({count} links)")

        return stats


# ============================================================================
# MAIN PIPELINE
# ============================================================================

def run_upload_pipeline(upload_only: bool = False, dry_run: bool = False):
    """Run the full upload and link insertion pipeline."""

    print("=" * 60)
    print("GOOGLE DRIVE UPLOAD + LINK INSERTION PIPELINE")
    print("=" * 60)

    if dry_run:
        print("*** DRY RUN MODE - No changes will be made ***\n")

    # Check config
    if CONFIG['gdrive_folder_id'] == 'YOUR_FOLDER_ID_HERE':
        print("ERROR: You need to set gdrive_folder_id in the CONFIG!")
        print("Edit gdrive_uploader.py and set your Google Drive folder ID.")
        return

    if not Path(CONFIG['credentials_file']).exists():
        print(f"ERROR: Credentials file not found: {CONFIG['credentials_file']}")
        print("See GOOGLE_DRIVE_SETUP.md for setup instructions.")
        return

    # Initialize
    if not dry_run:
        uploader = GoogleDriveUploader(
            CONFIG['credentials_file'],
            CONFIG['gdrive_folder_id']
        )

    link_map = LinkMapManager(CONFIG['link_map_file'])

    # Step 1: Upload audio files
    print("\n--- STEP 1: Upload Audio Files ---")
    audio_dir = Path(CONFIG['audio_source_dir'])

    if not audio_dir.exists():
        print(f"Audio directory not found: {audio_dir}")
        return

    audio_files = list(audio_dir.rglob('*.mp3'))
    print(f"Found {len(audio_files)} audio files")

    uploaded = 0
    for audio_file in audio_files:
        filename = audio_file.name
        print(f"\n  Processing: {filename}")

        if dry_run:
            print(f"    Would upload: {audio_file}")
            uploaded += 1
        else:
            try:
                file_info = uploader.upload_file(audio_file, filename)
                link_map.add(filename, file_info)
                uploaded += 1
            except Exception as e:
                print(f"    ERROR: {e}")

    if not dry_run:
        link_map.save()

    print(f"\n✓ Uploaded {uploaded} files")

    if upload_only:
        print("\n--- Upload Only Mode - Skipping paper updates ---")
        return

    # Step 2: Update papers with links
    print("\n--- STEP 2: Insert Links into Papers ---")
    papers_dir = Path(CONFIG['papers_dir'])

    if not papers_dir.exists():
        print(f"Papers directory not found: {papers_dir}")
        return

    updater = PaperUpdater(link_map, CONFIG['audio_patterns'])
    stats = updater.update_folder(papers_dir, dry_run)

    print(f"\n✓ Checked {stats['files_checked']} files")
    print(f"✓ Updated {stats['files_updated']} files")
    print(f"✓ Inserted {stats['links_inserted']} links")

    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE!")
    print("=" * 60)


# ============================================================================
# CLI
# ============================================================================

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Upload audio to Google Drive and insert links into papers')
    parser.add_argument('--upload-only', action='store_true', help='Only upload, skip link insertion')
    parser.add_argument('--dry-run', action='store_true', help='Show what would happen without making changes')

    args = parser.parse_args()

    run_upload_pipeline(
        upload_only=args.upload_only,
        dry_run=args.dry_run
    )
