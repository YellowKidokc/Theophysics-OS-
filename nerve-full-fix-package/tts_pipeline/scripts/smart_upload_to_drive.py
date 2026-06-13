"""
Smart Upload to Google Drive
=============================
Automatically uploads TTS audio to the correct Google Drive folder
(matching where the paper lives), gets shareable link, inserts into paper,
and cleans up local audio file.

Workflow:
    1. Scans OUTBOX for MP3 files
    2. Matches each MP3 to its source paper (strips _MTL_TTS suffix)
    3. Finds the paper's folder in your local structure
    4. Uploads to the matching folder in Google Drive
    5. Gets shareable link
    6. Inserts link into the local paper
    7. Deletes local MP3 (it's in Drive now)

Usage:
    python smart_upload_to_drive.py              # Process all audio in OUTBOX
    python smart_upload_to_drive.py --dry-run    # Show what would happen
    python smart_upload_to_drive.py --keep-local # Don't delete local files

Author: Theophysics Project
"""

import os
import sys
import json
import re
from pathlib import Path
from datetime import datetime

# ============================================================================
# CONFIGURATION
# ============================================================================

CONFIG = {
    # Where TTS outputs land
    'outbox': 'O:/Theophysics_Backend/TTS_Engines/TTS_Pipeline/OUTBOX',

    # Where your papers live (to search for matching .md files)
    'papers_root': 'O:/_THEO/THEO/TM SUBSTACK/TM SUBSTACK/03_PUBLICATIONS',

    # Google Drive settings
    'gdrive_credentials': 'O:/Theophysics_Data/google-drive-credentials.json',
    'gdrive_root_folder_id': '1Wpj3KM5-tzkCk1zfOg4MVuRbzjMw83aZ',

    # Upload all audio to this existing folder (owned by your account, not the service account)
    # This is your 08_Audio folder inside the project
    'gdrive_audio_folder_id': '1zYMngrdCrvs0le73Fgl8iODnAhWBLlia',

    # Link tracking
    'link_map_file': 'O:/Theophysics_Data/audio_link_map.json',

    # Audio file suffix patterns to strip when matching
    'audio_suffixes': ['_MTL_TTS', '_TTS', '_normalized', '_READ_ALOUD'],

    # Extensions to search for papers
    'paper_extensions': ['.md', '.txt'],
}

# ============================================================================
# GOOGLE DRIVE CLIENT
# ============================================================================

class DriveClient:
    """Handles Google Drive operations."""

    def __init__(self, credentials_file: str, root_folder_id: str):
        self.root_folder_id = root_folder_id
        self.service = None
        self.folder_cache = {}  # Cache folder IDs to avoid repeated lookups
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
                scopes=['https://www.googleapis.com/auth/drive']
            )
            self.service = build('drive', 'v3', credentials=credentials)
            print("[OK] Google Drive API connected")

        except ImportError:
            print("[ERROR] Google API not installed.")
            print("Run: pip install google-auth google-api-python-client")
            sys.exit(1)
        except Exception as e:
            print(f"[ERROR] Google Drive init failed: {e}")
            sys.exit(1)

    def find_or_create_folder(self, folder_path: str, parent_id: str = None) -> str:
        """
        Find or create a folder path in Drive.
        folder_path: like "03_Historical_Analysis/1940s"
        Returns the folder ID.
        """
        if parent_id is None:
            parent_id = self.root_folder_id

        # Check cache
        cache_key = f"{parent_id}/{folder_path}"
        if cache_key in self.folder_cache:
            return self.folder_cache[cache_key]

        parts = folder_path.strip('/').split('/')
        current_parent = parent_id

        for part in parts:
            if not part:
                continue

            # Search for existing folder
            query = f"name='{part}' and '{current_parent}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
            results = self.service.files().list(q=query, fields='files(id, name)').execute()
            files = results.get('files', [])

            if files:
                current_parent = files[0]['id']
            else:
                # Create folder
                folder_metadata = {
                    'name': part,
                    'mimeType': 'application/vnd.google-apps.folder',
                    'parents': [current_parent]
                }
                folder = self.service.files().create(
                    body=folder_metadata,
                    fields='id'
                ).execute()
                current_parent = folder['id']
                print(f"  [CREATED] Drive folder: {part}")

        self.folder_cache[cache_key] = current_parent
        return current_parent

    def upload_file(self, local_path: Path, folder_id: str) -> dict:
        """Upload file to specific folder and return file info with link."""

        # Check if already exists
        query = f"name='{local_path.name}' and '{folder_id}' in parents and trashed=false"
        results = self.service.files().list(
            q=query,
            fields='files(id, name, webViewLink)'
        ).execute()

        if results.get('files'):
            existing = results['files'][0]
            print(f"  [SKIP] Already in Drive: {local_path.name}")
            return existing

        # Upload
        file_metadata = {
            'name': local_path.name,
            'parents': [folder_id]
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

        # Get updated info with link
        file = self.service.files().get(
            fileId=file['id'],
            fields='id, name, webViewLink, webContentLink'
        ).execute()

        print(f"  [UPLOADED] {local_path.name}")
        return file


# ============================================================================
# PAPER MATCHER
# ============================================================================

class PaperMatcher:
    """Finds the source paper for an audio file."""

    def __init__(self, papers_root: str, audio_suffixes: list, paper_extensions: list):
        self.papers_root = Path(papers_root)
        self.audio_suffixes = audio_suffixes
        self.paper_extensions = paper_extensions
        self.paper_index = self._build_index()

    def _build_index(self) -> dict:
        """Build index of all papers: base_name -> full_path."""
        index = {}

        for ext in self.paper_extensions:
            for paper_path in self.papers_root.rglob(f'*{ext}'):
                # Skip hidden files and common non-paper files
                if paper_path.name.startswith('.'):
                    continue
                if any(skip in str(paper_path) for skip in ['node_modules', '__pycache__', '.git']):
                    continue

                base_name = paper_path.stem.lower()
                index[base_name] = paper_path

        print(f"[OK] Indexed {len(index)} papers")
        return index

    def get_base_name(self, audio_filename: str) -> str:
        """Strip audio suffixes to get base paper name."""
        name = Path(audio_filename).stem

        for suffix in self.audio_suffixes:
            if name.endswith(suffix):
                name = name[:-len(suffix)]
            # Also try case-insensitive
            if name.lower().endswith(suffix.lower()):
                name = name[:-len(suffix)]

        return name

    def find_paper(self, audio_filename: str) -> Path:
        """Find the paper that matches this audio file."""
        base_name = self.get_base_name(audio_filename).lower()

        # Direct match
        if base_name in self.paper_index:
            return self.paper_index[base_name]

        # Fuzzy match - look for papers containing this name
        for paper_base, paper_path in self.paper_index.items():
            if base_name in paper_base or paper_base in base_name:
                return paper_path

        return None

    def get_relative_folder(self, paper_path: Path) -> str:
        """Get the folder path relative to papers_root."""
        try:
            rel_path = paper_path.parent.relative_to(self.papers_root)
            return str(rel_path).replace('\\', '/')
        except ValueError:
            return ""


# ============================================================================
# LINK INSERTER
# ============================================================================

class LinkInserter:
    """Inserts audio links into papers."""

    # Where to insert the link in the paper
    LINK_PATTERNS = [
        # After title (# Title)
        (r'^(# .+)$', r'\1\n\n[Listen to Audio]({{LINK}})'),
        # After YAML frontmatter
        (r'^(---\n.*?\n---)', r'\1\n\n[Listen to Audio]({{LINK}})'),
    ]

    def insert_link(self, paper_path: Path, audio_link: str, audio_filename: str) -> bool:
        """Insert audio link into paper. Returns True if modified."""

        with open(paper_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check if link already exists
        if audio_link in content or audio_filename in content:
            print(f"  [SKIP] Link already in paper")
            return False

        # Create the link markdown
        link_text = f"\n\n> [Listen to Audio]({audio_link})\n"

        # Try to insert after title
        title_match = re.search(r'^# .+$', content, re.MULTILINE)
        if title_match:
            insert_pos = title_match.end()
            new_content = content[:insert_pos] + link_text + content[insert_pos:]
        else:
            # Insert at beginning
            new_content = link_text + content

        with open(paper_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

        print(f"  [LINKED] Added to: {paper_path.name}")
        return True


# ============================================================================
# LINK MAP MANAGER
# ============================================================================

class LinkMapManager:
    """Tracks all audio -> link mappings."""

    def __init__(self, map_file: str):
        self.map_file = Path(map_file)
        self.links = self._load()

    def _load(self) -> dict:
        if self.map_file.exists():
            with open(self.map_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def save(self):
        self.map_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.map_file, 'w', encoding='utf-8') as f:
            json.dump(self.links, f, indent=2)

    def add(self, audio_filename: str, file_info: dict, paper_path: str, drive_folder: str):
        self.links[audio_filename] = {
            'drive_id': file_info.get('id'),
            'view_link': file_info.get('webViewLink'),
            'download_link': file_info.get('webContentLink'),
            'paper': paper_path,
            'drive_folder': drive_folder,
            'uploaded': datetime.now().isoformat()
        }


# ============================================================================
# MAIN PROCESSOR
# ============================================================================

def process_audio_files(dry_run: bool = False, keep_local: bool = False):
    """Main processing function."""

    print("=" * 60)
    print("SMART UPLOAD TO GOOGLE DRIVE")
    print("=" * 60)

    if dry_run:
        print("[DRY RUN] No changes will be made\n")

    outbox = Path(CONFIG['outbox'])

    if not outbox.exists():
        print(f"[ERROR] OUTBOX not found: {outbox}")
        return

    # Find audio files
    audio_files = list(outbox.glob('*.mp3')) + list(outbox.glob('*.wav'))

    if not audio_files:
        print(f"\n[INFO] No audio files in OUTBOX")
        print(f"       Path: {outbox}")
        return

    print(f"\nFound {len(audio_files)} audio file(s) to process\n")

    # Initialize components
    if not dry_run:
        drive = DriveClient(CONFIG['gdrive_credentials'], CONFIG['gdrive_root_folder_id'])

    matcher = PaperMatcher(
        CONFIG['papers_root'],
        CONFIG['audio_suffixes'],
        CONFIG['paper_extensions']
    )

    inserter = LinkInserter()
    link_map = LinkMapManager(CONFIG['link_map_file'])

    # Process each audio file
    stats = {'uploaded': 0, 'linked': 0, 'deleted': 0, 'skipped': 0, 'errors': 0}

    for audio_path in audio_files:
        print(f"\n--- Processing: {audio_path.name} ---")

        # Find matching paper
        paper_path = matcher.find_paper(audio_path.name)

        if not paper_path:
            print(f"  [WARNING] No matching paper found")
            print(f"            Looked for: {matcher.get_base_name(audio_path.name)}")
            stats['skipped'] += 1
            continue

        print(f"  [MATCH] Paper: {paper_path.name}")

        # Get relative folder path
        rel_folder = matcher.get_relative_folder(paper_path)
        print(f"  [FOLDER] {rel_folder or '(root)'}")

        if dry_run:
            print(f"  [DRY RUN] Would upload to Drive: 08_Audio folder")
            print(f"  [DRY RUN] Would insert link into: {paper_path.name}")
            if not keep_local:
                print(f"  [DRY RUN] Would delete local: {audio_path.name}")
            stats['uploaded'] += 1
            continue

        try:
            # Upload to the existing 08_Audio folder (owned by user's account)
            # Service accounts can't create folders (no storage quota)
            # but CAN upload to folders owned by real accounts
            folder_id = CONFIG['gdrive_audio_folder_id']

            # Upload
            file_info = drive.upload_file(audio_path, folder_id)
            stats['uploaded'] += 1

            # Get link
            audio_link = file_info.get('webViewLink')

            if audio_link:
                # Insert link into paper
                if inserter.insert_link(paper_path, audio_link, audio_path.name):
                    stats['linked'] += 1

                # Save to link map
                link_map.add(audio_path.name, file_info, str(paper_path), rel_folder)

                print(f"  [LINK] {audio_link}")

            # Delete local file
            if not keep_local:
                audio_path.unlink()
                print(f"  [DELETED] Local file removed")
                stats['deleted'] += 1

        except Exception as e:
            print(f"  [ERROR] {e}")
            stats['errors'] += 1

    # Save link map
    if not dry_run:
        link_map.save()
        print(f"\n[OK] Link map saved: {CONFIG['link_map_file']}")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Uploaded:  {stats['uploaded']}")
    print(f"  Linked:    {stats['linked']}")
    print(f"  Deleted:   {stats['deleted']}")
    print(f"  Skipped:   {stats['skipped']}")
    print(f"  Errors:    {stats['errors']}")
    print("=" * 60)


# ============================================================================
# CLI
# ============================================================================

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Smart Upload TTS Audio to Google Drive')
    parser.add_argument('--dry-run', action='store_true', help='Show what would happen without making changes')
    parser.add_argument('--keep-local', action='store_true', help='Keep local audio files after upload')

    args = parser.parse_args()

    process_audio_files(dry_run=args.dry_run, keep_local=args.keep_local)
