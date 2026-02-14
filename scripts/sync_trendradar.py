#!/usr/bin/env python3
"""Clone or pull the TrendRadar subproject into engine/trendradar."""

import os
import subprocess
import sys

REPO_URL = "https://github.com/sansan0/TrendRadar.git"
TARGET_DIR = os.path.join(os.path.dirname(__file__), "..", "engine", "trendradar")


def run(cmd, cwd=None):
    print(f"[sync_trendradar] {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd)
    if result.returncode != 0:
        print(f"[sync_trendradar] WARNING: command exited with code {result.returncode}")
    return result.returncode


def main():
    target = os.path.abspath(TARGET_DIR)

    if os.path.isdir(os.path.join(target, ".git")):
        print(f"[sync_trendradar] Pulling latest changes in {target}")
        run(["git", "pull", "--rebase"], cwd=target)
    else:
        print(f"[sync_trendradar] Cloning {REPO_URL} into {target}")
        os.makedirs(os.path.dirname(target), exist_ok=True)
        run(["git", "clone", REPO_URL, target])


if __name__ == "__main__":
    main()
