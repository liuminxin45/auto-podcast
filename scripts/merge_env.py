#!/usr/bin/env python3
"""
Merge all .env* files into a single backup configuration file.

Usage:
    python scripts/merge_env.py                    # Output to .env.backup
    python scripts/merge_env.py -o custom.env      # Output to custom file
    python scripts/merge_env.py --dry-run          # Preview without writing
"""

import argparse
import os
from pathlib import Path
from datetime import datetime


def find_env_files(root_dir: Path) -> list[Path]:
    """Find all .env* files in the root directory."""
    env_files = []
    
    # Main .env file
    main_env = root_dir / ".env"
    if main_env.exists():
        env_files.append(main_env)
    
    # All .env.* overlay files
    for file in sorted(root_dir.glob(".env.*")):
        if file.is_file() and not file.name.endswith(('.example', '.backup', '.bak')):
            env_files.append(file)
    
    return env_files


def read_env_file(file_path: Path) -> list[str]:
    """Read an env file and return its lines."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.readlines()
    except Exception as e:
        print(f"Warning: Failed to read {file_path}: {e}")
        return []


def merge_env_files(env_files: list[Path]) -> str:
    """Merge multiple env files into a single configuration."""
    output_lines = []
    
    # Header
    output_lines.append("# =============================\n")
    output_lines.append("# Merged Environment Configuration\n")
    output_lines.append(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    output_lines.append("# =============================\n")
    output_lines.append("#\n")
    output_lines.append("# This file contains all configurations from:\n")
    for env_file in env_files:
        output_lines.append(f"#   - {env_file.name}\n")
    output_lines.append("#\n")
    output_lines.append("# To restore:\n")
    output_lines.append("#   1. Split this file back into individual .env* files\n")
    output_lines.append("#   2. Or use this as your main .env (not recommended for mode switching)\n")
    output_lines.append("# =============================\n")
    output_lines.append("\n")
    
    # Process each file
    for env_file in env_files:
        output_lines.append(f"# =============================\n")
        output_lines.append(f"# Source: {env_file.name}\n")
        output_lines.append(f"# =============================\n")
        
        lines = read_env_file(env_file)
        if lines:
            output_lines.extend(lines)
            # Ensure trailing newline
            if lines and not lines[-1].endswith('\n'):
                output_lines.append('\n')
        
        output_lines.append("\n")
    
    return ''.join(output_lines)


def main():
    parser = argparse.ArgumentParser(
        description='Merge all .env* files into a single backup configuration.'
    )
    parser.add_argument(
        '-o', '--output',
        default='.env.backup',
        help='Output file path (default: .env.backup)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview the merged content without writing to file'
    )
    parser.add_argument(
        '--root',
        type=Path,
        default=Path.cwd(),
        help='Root directory to search for .env files (default: current directory)'
    )
    
    args = parser.parse_args()
    
    # Find all env files
    root_dir = args.root
    env_files = find_env_files(root_dir)
    
    if not env_files:
        print(f"No .env files found in {root_dir}")
        return 1
    
    print(f"Found {len(env_files)} .env file(s):")
    for env_file in env_files:
        print(f"  - {env_file.name}")
    print()
    
    # Merge files
    merged_content = merge_env_files(env_files)
    
    # Output
    if args.dry_run:
        print("=== Merged Content (Dry Run) ===")
        print(merged_content)
    else:
        output_path = root_dir / args.output
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(merged_content)
            print(f"✓ Successfully merged {len(env_files)} file(s) into: {output_path}")
            print(f"  Total size: {len(merged_content)} bytes")
        except Exception as e:
            print(f"✗ Failed to write output file: {e}")
            return 1
    
    return 0


if __name__ == '__main__':
    exit(main())
