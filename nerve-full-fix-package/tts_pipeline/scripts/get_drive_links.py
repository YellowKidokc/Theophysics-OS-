#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Get Google Drive Links + Insert into Papers
============================================
Scans your Google Drive 08_Audio folder for audio files,
gets shareable links, and inserts them into matching papers.

Use this AFTER GoodSync has synced your audio files to Drive.

Workflow:
    1. TTS creates audio in OUTBOX
    2. GoodSync syncs OUTBOX → Drive/08_Audio
    3. Run THIS script to:
       - Get shareable links for all audio in Drive
       - Match each audio to its source paper
       - Insert links into papers

Usage:
    python get_drive_links.py              # Get links and insert into papers
    python get_drive_links.py --dry-run    # Show what would happen
    python get_drive_links.py --list       # Just list audio files in Drive

Author: Theophysics Project
"""

import os
import sys
import json
import re
from pathlib import Path
from datetime import datetime

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ============================================================================
# CONFIGURATION
# ============================================================================

CONFIG = {
    # Where TTS outputs land (for cleanup after sync)
    'outbox': 'O:/Theophysics_Backend/TTS_Engines/TTS_Pipeline/OUTBOX',

    # Where your papers live (to search for matching .md files)
    # Scan the whole TM SUBSTACK folder to find all papers
    'papers_root': 'O:/_THEO/THEO/TM SUBSTACK',

    # Google Drive settings
    'gdrive_credentials': 'O:/Theophysics_Data/google-drive-credentials.json',
    'gdrive_audio_folder_id': '1M8kS47sMtiz5Zr0lDepxXGoV-P2IcoQ9',  # 00-Audio_TTS_LOGOS root folder

    # Link tracking
    'link_map_file': 'O:/Theophysics_Data/audio_link_map.json',

    # Audio file suffix patterns to strip when matching to papers
    'audio_suffixes': ['_MTL_TTS', '_TTS', '_normalized', '_READ_ALOUD'],

    # Extensions to search for papers
    'paper_extensions': ['.md', '.txt'],
}

# ============================================================================
# GOOGLE DRIVE CLIENT
# ============================================================================

class DriveClient:
    """Handles Google Drive operations (read-only for links)."""

    def __init__(self, credentials_file: str):
        self.service = None
        self._init_service(credentials_file)

    def _init_service(self, credentials_file: str):
        """Initialize Google Drive API."""
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build

            credentials = service_account.Credentials.from_service_account_file(
                credentials_file,
                scopes=['https://www.googleapis.com/auth/drive.readonly']
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

    def get_audio_files(self, folder_id: str = None, scan_all: bool = False) -> list:
        """Get all audio files. If scan_all=True, searches entire accessible Drive."""
        files = []
        page_token = None

        while True:
            if scan_all:
                # Search ALL folders the service account can access
                query = "(mimeType='audio/mpeg' or mimeType='audio/wav') and trashed=false"
            else:
                query = f"'{folder_id}' in parents and (mimeType='audio/mpeg' or mimeType='audio/wav' or name contains '.mp3' or name contains '.wav') and trashed=false"

            results = self.service.files().list(
                q=query,
                pageSize=500,
                fields="nextPageToken, files(id, name, webViewLink, webContentLink, createdTime)",
                pageToken=page_token
            ).execute()

            files.extend(results.get('files', []))
            page_token = results.get('nextPageToken')

            if not page_token:
                break

        return files

    def make_shareable(self, file_id: str) -> str:
        """Make file shareable and return link (if not already)."""
        try:
            # Check current permissions
            perms = self.service.permissions().list(fileId=file_id).execute()
            is_public = any(p.get('type') == 'anyone' for p in perms.get('permissions', []))

            if not is_public:
                # Note: This requires write access which service account may not have
                # In that case, you'll need to manually share the folder in Drive
                print(f"  [INFO] File not public - share 08_Audio folder with 'Anyone with link'")

            # Get the link
            file = self.service.files().get(
                fileId=file_id,
                fields='webViewLink, webContentLink'
            ).execute()

            return file.get('webViewLink')

        except Exception as e:
            print(f"  [WARNING] Could not get link: {e}")
            return None


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
            if name.lower().endswith(suffix.lower()):
                name = name[:-len(suffix)]

        return name

    def find_paper(self, audio_filename: str) -> Path:
        """Find the paper that matches this audio file."""
        base_name = self.get_base_name(audio_filename).lower()

        # Direct match
        if base_name in self.paper_index:
            return self.paper_index[base_name]

        # Fuzzy match
        for paper_base, paper_path in self.paper_index.items():
            if base_name in paper_base or paper_base in base_name:
                return paper_path

        return None


# ============================================================================
# LINK INSERTER
# ============================================================================

class LinkInserter:
    """Inserts audio links into papers using templates."""

    # Expanded template for papers starting with 0 (indexes, main papers)
    EXPANDED_TEMPLATE = '''
> [!example]+ **Content Portal**
>
> #### Listen to Audio
> *Have this paper read to you*
> [Play Audio]({audio_link})
'''

    # Simplified template for other papers
    SIMPLE_TEMPLATE = '''
> [!info] **Quick Access:** [Listen to Audio]({audio_link})
'''

    def insert_link(self, paper_path: Path, audio_link: str, audio_filename: str, refresh: bool = False) -> bool:
        """Insert audio link into paper. Returns True if modified."""

        with open(paper_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check if this exact link already exists
        if audio_link in content:
            print(f"  [SKIP] Link already in paper")
            return False

        # Check if there's an OLD audio link that needs updating (various formats)
        old_patterns = [
            r'> \[Listen to Audio\]\(https://drive\.google\.com/[^)]+\)',
            r'> \[!info\][^\n]*\[Listen to Audio\]\(https://drive\.google\.com/[^)]+\)',
            r'> \[!example\]\+[^>]*\[Play Audio\]\(https://drive\.google\.com/[^)]+\)',
            r'\[Play Audio\]\(https://drive\.google\.com/[^)]+\)',
        ]

        has_old_link = False
        for pattern in old_patterns:
            if re.search(pattern, content, re.DOTALL):
                has_old_link = True
                break

        if has_old_link and refresh:
            # Remove old content portal block if exists
            content = re.sub(r'\n*> \[!example\]\+ \*\*Content Portal\*\*.*?\n(?=> \[!|\n[^>]|\Z)', '\n', content, flags=re.DOTALL)
            content = re.sub(r'\n*> \[!info\][^\n]*\n', '\n', content)
            content = re.sub(r'\n*> \[Listen to Audio\]\([^)]+\)\n*', '\n', content)
        elif has_old_link:
            print(f"  [SKIP] Paper has audio link (use --refresh to update)")
            return False

        # Choose template based on filename
        # Papers starting with 00, 01, 02... (two digits) get expanded template
        paper_name = paper_path.stem
        if len(paper_name) >= 2 and paper_name[:2].isdigit():
            link_text = self.EXPANDED_TEMPLATE.format(audio_link=audio_link)
            template_type = "expanded"
        else:
            link_text = self.SIMPLE_TEMPLATE.format(audio_link=audio_link)
            template_type = "simple"

        # Try to insert after title
        title_match = re.search(r'^# .+$', content, re.MULTILINE)
        if title_match:
            insert_pos = title_match.end()
            new_content = content[:insert_pos] + link_text + content[insert_pos:]
        else:
            new_content = link_text + content

        with open(paper_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

        print(f"  [LINKED] Added ({template_type}) to: {paper_path.name}")
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

    def add(self, audio_filename: str, file_info: dict, paper_path: str):
        self.links[audio_filename] = {
            'drive_id': file_info.get('id'),
            'view_link': file_info.get('webViewLink'),
            'download_link': file_info.get('webContentLink'),
            'paper': paper_path,
            'synced': datetime.now().isoformat()
        }

    def is_processed(self, audio_filename: str) -> bool:
        """Check if we've already processed this file."""
        return audio_filename in self.links


# ============================================================================
# MAIN PROCESSOR
# ============================================================================

def process_drive_audio(dry_run: bool = False, list_only: bool = False, refresh: bool = False, scan_all: bool = False):
    """Main processing function."""

    print("=" * 60)
    print("GET DRIVE LINKS + INSERT INTO PAPERS")
    print("=" * 60)

    if dry_run:
        print("[DRY RUN] No changes will be made\n")

    # Initialize Drive client
    drive = DriveClient(CONFIG['gdrive_credentials'])

    # Get audio files from Drive
    if scan_all:
        print(f"\nScanning ALL Drive folders for audio...")
        audio_files = drive.get_audio_files(scan_all=True)
    else:
        print(f"\nScanning Drive folder: 00-Audio_TTS_LOGOS")
        audio_files = drive.get_audio_files(CONFIG['gdrive_audio_folder_id'])

    if not audio_files:
        print("\n[INFO] No audio files found in Drive/08_Audio")
        print("       Make sure GoodSync has synced your files first.")
        return

    print(f"Found {len(audio_files)} audio file(s) in Drive\n")

    if list_only:
        print("-" * 40)
        for f in audio_files:
            print(f"  {f['name']}")
            if f.get('webViewLink'):
                print(f"    Link: {f['webViewLink']}")
        print("-" * 40)
        return

    # Initialize other components
    matcher = PaperMatcher(
        CONFIG['papers_root'],
        CONFIG['audio_suffixes'],
        CONFIG['paper_extensions']
    )

    inserter = LinkInserter()
    link_map = LinkMapManager(CONFIG['link_map_file'])

    # Process each audio file
    stats = {'linked': 0, 'skipped': 0, 'no_match': 0}

    for audio_file in audio_files:
        filename = audio_file['name']
        # Handle Unicode characters for Windows console
        safe_filename = filename.encode('ascii', 'replace').decode('ascii')
        print(f"\n--- {safe_filename} ---")

        # Check if already processed (skip this check if refreshing)
        if link_map.is_processed(filename) and not refresh:
            print(f"  [SKIP] Already processed")
            stats['skipped'] += 1
            continue

        # Get the link
        link = audio_file.get('webViewLink')
        if not link:
            link = drive.make_shareable(audio_file['id'])

        if not link:
            print(f"  [WARNING] Could not get shareable link")
            stats['skipped'] += 1
            continue

        print(f"  [LINK] {link}")

        # Find matching paper
        paper_path = matcher.find_paper(filename)

        if not paper_path:
            print(f"  [WARNING] No matching paper found for: {matcher.get_base_name(filename)}")
            # Still save the link even without a paper match
            if not dry_run:
                link_map.add(filename, audio_file, "NO_MATCH")
            stats['no_match'] += 1
            continue

        safe_paper_name = paper_path.name.encode('ascii', 'replace').decode('ascii')
        print(f"  [MATCH] Paper: {safe_paper_name}")

        if dry_run:
            print(f"  [DRY RUN] Would insert link into: {paper_path.name}")
            stats['linked'] += 1
            continue

        # Insert link into paper
        if inserter.insert_link(paper_path, link, filename, refresh=refresh):
            stats['linked'] += 1

        # Save to link map
        link_map.add(filename, audio_file, str(paper_path))

    # Save link map
    if not dry_run:
        link_map.save()
        print(f"\n[OK] Link map saved: {CONFIG['link_map_file']}")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Links inserted: {stats['linked']}")
    print(f"  Skipped:        {stats['skipped']}")
    print(f"  No paper match: {stats['no_match']}")
    print("=" * 60)

    # Offer to clean up local files
    if not dry_run and not list_only and stats['linked'] > 0:
        cleanup_local_files(audio_files, link_map)


def cleanup_local_files(drive_files: list, link_map: LinkMapManager):
    """Offer to delete local files that are now in Drive."""

    outbox = Path(CONFIG['outbox'])
    if not outbox.exists():
        return

    # Find local files that match files in Drive
    local_files = list(outbox.glob('*.mp3')) + list(outbox.glob('*.wav'))
    drive_filenames = {f['name'] for f in drive_files}

    files_to_delete = [f for f in local_files if f.name in drive_filenames]

    if not files_to_delete:
        print("\n[INFO] No local files to clean up.")
        return

    print(f"\n" + "=" * 60)
    print("LOCAL FILE CLEANUP")
    print("=" * 60)
    print(f"\nFound {len(files_to_delete)} local file(s) that are now in Drive:")
    print("-" * 40)
    for f in files_to_delete:
        size_mb = f.stat().st_size / (1024 * 1024)
        print(f"  {f.name} ({size_mb:.1f} MB)")
    print("-" * 40)

    print("\nThese files are safely in Google Drive.")
    print("Delete local copies to free up space?")
    print()

    confirm = input("Type 'yes' to delete local files: ").strip().lower()

    if confirm == 'yes':
        deleted = 0
        for f in files_to_delete:
            try:
                f.unlink()
                print(f"  [DELETED] {f.name}")
                deleted += 1
            except Exception as e:
                print(f"  [ERROR] Could not delete {f.name}: {e}")
        print(f"\n[OK] Deleted {deleted} local file(s)")
    else:
        print("\n[SKIP] Local files kept.")


# ============================================================================
# CLI
# ============================================================================

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Get Drive Links and Insert into Papers')
    parser.add_argument('--dry-run', action='store_true', help='Show what would happen without making changes')
    parser.add_argument('--list', action='store_true', help='Just list audio files in Drive')
    parser.add_argument('--refresh', action='store_true', help='Update existing links (use after re-doing TTS)')
    parser.add_argument('--scan-all', action='store_true', help='Scan ALL Drive folders (not just audio folder)')

    args = parser.parse_args()

    process_drive_audio(dry_run=args.dry_run, list_only=args.list, refresh=args.refresh, scan_all=args.scan_all)
