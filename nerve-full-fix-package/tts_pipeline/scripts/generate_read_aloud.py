"""
Generate Read-Aloud Version of Markdown Files
==============================================
Injects audio translation callouts after equations based on a translation table.

Usage:
    python generate_read_aloud.py <input_markdown_file> [output_markdown_file]

Example:
    python generate_read_aloud.py "05_The_Academia/PAPER I (Public Version).md"
"""

import os
import sys
import re
import argparse

def normalize_text(text):
    """Normalizes text by removing extra whitespace."""
    return ' '.join(text.split()).strip()

def load_translation_map(map_file_path):
    """
    Loads the translation map from a tab-delimited file.
    Assumes structure: [Original String] [Tab] ... [Audio Script (Last Column)]
    Returns a list of tuples: (normalized_original, audio_script)
    """
    translations = []

    if not os.path.exists(map_file_path):
        print(f"Error: Map file not found at {map_file_path}")
        return []

    with open(map_file_path, 'r', encoding='utf-8') as f:
        for line in f:
            parts = line.split('\t')
            if len(parts) >= 2:
                original = parts[0].strip()
                audio_script = parts[-1].strip().strip('"')

                if original and audio_script:
                    translations.append((original, audio_script))

    # Sort by length (longest first) to prevent partial matches
    translations.sort(key=lambda x: len(x[0]), reverse=True)
    return translations

def process_markdown(input_file, output_file, translations):
    """
    Reads input markdown, finds equations from the map,
    inserts the audio callout, and writes to output file.
    """

    if not os.path.exists(input_file):
        print(f"Error: Input file not found at {input_file}")
        return

    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Add the Identifier tag at the top
    header_tag = "<!-- IDENTIFIER: READ_ALOUD_VERSION -->\n"
    if not content.startswith("<!-- IDENTIFIER"):
        content = header_tag + content

    match_count = 0

    for original, audio_script in translations:
        if original in content:
            callout = f'\n\n> **Audio Translation**\n>\n> *"{audio_script}"*\n'

            if callout.strip() not in content:
                replacement = f"{original}{callout}"
                content = content.replace(original, replacement)
                match_count += 1

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"Success! Processed {input_file} -> {output_file}")
    print(f"Injected {match_count} audio translations.")

def main():
    # Default paths - can be overridden
    base_dir = os.path.dirname(os.path.abspath(__file__))

    # Look for translation table in current directory or INBOX
    map_file_candidates = [
        os.path.join(base_dir, "MATH_TRANSLATION_TABLE.txt"),
        os.path.join(base_dir, "math_translations.txt"),
        os.path.join(base_dir, "INBOX", "math_translations.txt"),
    ]

    map_file = None
    for candidate in map_file_candidates:
        if os.path.exists(candidate):
            map_file = candidate
            break

    if not map_file:
        print("Error: No translation table found. Expected one of:")
        for c in map_file_candidates:
            print(f"  - {c}")
        return

    print(f"Loading translations from: {map_file}")
    translations = load_translation_map(map_file)
    print(f"Loaded {len(translations)} translation pairs.")

    # If no arguments, process all MD files in INBOX
    if len(sys.argv) < 2:
        print("No input file specified. Processing all .md files in INBOX/ folder...")
        inbox = os.path.join(base_dir, "INBOX")
        
        if not os.path.exists(inbox):
            print(f"Error: INBOX directory not found at {inbox}")
            return
        
        # Find all MD files recursively
        md_files = []
        for root, dirs, files in os.walk(inbox):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for filename in files:
                if filename.lower().endswith('.md'):
                    full_path = os.path.join(root, filename)
                    # Skip files that are already READ_ALOUD versions
                    if '_READ_ALOUD' not in filename:
                        md_files.append(full_path)
        
        if not md_files:
            print("No .md files found in INBOX directory.")
            return
        
        print(f"Found {len(md_files)} file(s) to process:\n")
        
        # Process each file
        for i, input_path in enumerate(md_files, 1):
            print(f"\n[{i}/{len(md_files)}] Processing: {os.path.basename(input_path)}")
            
            # Generate output path
            dir_name = os.path.dirname(input_path)
            base_name = os.path.basename(input_path)
            name_part, ext = os.path.splitext(base_name)
            output_path = os.path.join(dir_name, f"{name_part}_READ_ALOUD{ext}")
            
            # Skip if output already exists
            if os.path.exists(output_path):
                print(f"  [SKIP] Output already exists: {os.path.basename(output_path)}")
                continue
            
            try:
                process_markdown(input_path, output_path, translations)
            except Exception as e:
                print(f"  [ERROR] Failed to process: {e}")
        
        print(f"\n\nCompleted processing {len(md_files)} file(s).")
        return

    # Single file mode
    input_path = sys.argv[1]

    # Check if it's a relative path to INBOX
    if not os.path.isabs(input_path):
        inbox_path = os.path.join(base_dir, "INBOX", input_path)
        if os.path.exists(inbox_path):
            input_path = inbox_path

    if len(sys.argv) >= 3:
        output_path = sys.argv[2]
    else:
        dir_name = os.path.dirname(input_path) or base_dir
        base_name = os.path.basename(input_path)
        name_part, ext = os.path.splitext(base_name)
        output_path = os.path.join(dir_name, f"{name_part}_READ_ALOUD{ext}")

    print(f"Processing: {input_path}")
    process_markdown(input_path, output_path, translations)

if __name__ == "__main__":
    main()
