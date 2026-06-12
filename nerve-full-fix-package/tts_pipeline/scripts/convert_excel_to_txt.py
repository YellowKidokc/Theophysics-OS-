"""
Convert Excel translation table to tab-delimited text format
===========================================================
Converts MATH_TRANSLATION_MASTER.xlsx to MATH_TRANSLATION_TABLE.txt
Uses the consolidated master file with all translation data.
"""

import pandas as pd
import os
import sys

def convert_excel_to_txt(excel_path, txt_path):
    """Convert Excel file to tab-delimited text file."""

    if not os.path.exists(excel_path):
        print(f"Error: Excel file not found at {excel_path}")
        return False

    try:
        # Read Excel file
        print(f"Reading Excel file: {excel_path}")
        df = pd.read_excel(excel_path)

        # Check the structure
        print(f"Columns found: {list(df.columns)}")
        print(f"Shape: {df.shape[0]} rows x {df.shape[1]} columns")

        # Assume first column is original, last column is audio script
        # This matches the expected format in generate_read_aloud.py
        if df.shape[1] >= 2:
            # Write tab-delimited format
            with open(txt_path, 'w', encoding='utf-8') as f:
                for index, row in df.iterrows():
                    # Get first column (original) and last column (audio script)
                    original = str(row.iloc[0]).strip()
                    audio_script = str(row.iloc[-1]).strip()

                    if original and audio_script and original != 'nan' and audio_script != 'nan':
                        # Write tab-delimited line
                        f.write(f"{original}\t{audio_script}\n")

            print(f"Success! Converted to: {txt_path}")
            print(f"Total translation pairs: {len(df)}")
            return True
        else:
            print("Error: Excel file must have at least 2 columns")
            return False

    except Exception as e:
        print(f"Error converting Excel file: {e}")
        return False

def main():
    # Use the new consolidated master file
    script_dir = os.path.dirname(__file__)
    excel_path = os.path.join(script_dir, "MATH_TRANSLATION_MASTER.xlsx")
    txt_path = os.path.join(script_dir, "MATH_TRANSLATION_TABLE.txt")

    print("Converting Excel translation table to text format...")
    print(f"Source: {excel_path}")
    print(f"Output: {txt_path}")
    
    if not os.path.exists(excel_path):
        print(f"\n[ERROR] Master Excel file not found: {excel_path}")
        print("[INFO] Run consolidate_excel_files.py first to create the master file.")
        sys.exit(1)
    
    success = convert_excel_to_txt(excel_path, txt_path)

    if success:
        print(f"\nConversion complete! Translation table saved as: {txt_path}")
    else:
        print("\nConversion failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
