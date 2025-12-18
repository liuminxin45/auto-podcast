#!/usr/bin/env python3
"""
Split a merged .env.backup file back into individual .env* files.

Usage:
    python scripts/split_env.py .env.backup         # Restore from backup
    python scripts/split_env.py custom.env          # Restore from custom file
    python scripts/split_env.py --dry-run backup    # Preview without writing
"""

import argparse
import re
from pathlib import Path
from typing import Dict, List


def parse_merged_env(content: str) -> Dict[str, List[str]]:
    """Parse a merged env file and split by source markers."""
    files = {}
    current_file = None
    current_lines = []
    
    # Pattern to match source markers: # Source: .env.xxx
    source_pattern = re.compile(r'^#\s*Source:\s*(.+\.env[^\s]*)\s*$')
    
    for line in content.split('\n'):
        match = source_pattern.match(line)
        if match:
            # Save previous file if exists
            if current_file and current_lines:
                files[current_file] = current_lines
            
            # Start new file
            current_file = match.group(1).strip()
            current_lines = []
        elif current_file:
            # Skip separator lines after source marker
            if line.strip() == '# =============================' or \
               line.strip() == '#' * 29:
                continue
            # Add line to current file
            current_lines.append(line)
    
    # Save last file
    if current_file and current_lines:
        files[current_file] = current_lines
    
    # Clean up trailing empty lines
    for filename in files:
        while files[filename] and not files[filename][-1].strip():
            files[filename].pop()
    
    return files


def split_env_file(input_path: Path, output_dir: Path, dry_run: bool = False) -> int:
    """Split a merged env file back into individual files."""
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"✗ Failed to read input file: {e}")
        return 1
    
    # Parse the merged file
    files = parse_merged_env(content)
    
    if not files:
        print("✗ No source markers found in the input file.")
        print("   Expected format: # Source: .env.xxx")
        return 1
    
    print(f"Found {len(files)} file(s) to restore:")
    for filename in files:
        print(f"  - {filename} ({len(files[filename])} lines)")
    print()
    
    # Write files
    if dry_run:
        print("=== Dry Run: Preview ===")
        for filename, lines in files.items():
            print(f"\n--- {filename} ---")
            print('\n'.join(lines[:10]))
            if len(lines) > 10:
                print(f"... ({len(lines) - 10} more lines)")
    else:
        success_count = 0
        for filename, lines in files.items():
            output_path = output_dir / filename
            try:
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(lines))
                    if lines:  # Add trailing newline
                        f.write('\n')
                print(f"✓ Restored: {output_path}")
                success_count += 1
            except Exception as e:
                print(f"✗ Failed to write {output_path}: {e}")
        
        print(f"\n✓ Successfully restored {success_count}/{len(files)} file(s)")
    
    return 0


def main():
    parser = argparse.ArgumentParser(
        description='Split a merged .env.backup file back into individual .env* files.'
    )
    parser.add_argument(
        'input',
        type=Path,
        help='Input merged env file (e.g., .env.backup)'
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=Path.cwd(),
        help='Output directory for restored files (default: current directory)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview the split without writing files'
    )
    
    args = parser.parse_args()
    
    if not args.input.exists():
        print(f"✗ Input file not found: {args.input}")
        return 1
    
    return split_env_file(args.input, args.output_dir, args.dry_run)


if __name__ == '__main__':
    exit(main())
