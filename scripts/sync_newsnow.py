#!/usr/bin/env python3
"""Synchronize the NewsNow source service into engine/newsnow.

NewsNow is kept as an external data-source service for TrendRadar. This script
fetches/checks out the source tree. Dependency install and runtime startup are
explicit steps handled by scripts/newsnow_runtime.js.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
from pathlib import Path

REPO_URL = "https://github.com/ourongxing/newsnow.git"
ROOT_DIR = Path(__file__).resolve().parent.parent
TARGET_DIR = ROOT_DIR / "engine" / "newsnow"
LOCK_FILE = ROOT_DIR / "engine" / "newsnow.lock.json"
COMMAND_TIMEOUT_SECONDS = int(os.environ.get("NEWSNOW_SYNC_TIMEOUT", "180"))


def command_env(no_proxy: bool = False) -> dict[str, str]:
    env = os.environ.copy()
    if no_proxy:
        for key in (
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "http_proxy",
            "https_proxy",
            "ALL_PROXY",
            "all_proxy",
        ):
            env.pop(key, None)
        env["NO_PROXY"] = "*"
        env["no_proxy"] = "*"
    return env


def git_cmd(args: list[str], no_proxy: bool = False) -> list[str]:
    if no_proxy:
        return ["git", "-c", "http.proxy=", "-c", "https.proxy=", *args]
    return ["git", *args]


def kill_process_tree(process: subprocess.Popen[str]) -> None:
    if sys.platform.startswith("win"):
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return

    try:
        os.killpg(process.pid, signal.SIGTERM)
    except Exception:
        process.kill()


def run(
    cmd: list[str],
    cwd: Path | None = None,
    check: bool = False,
    timeout: int = COMMAND_TIMEOUT_SECONDS,
    no_proxy: bool = False,
) -> int:
    print(f"[sync_newsnow] {' '.join(cmd)}")
    try:
        process = subprocess.Popen(
            cmd,
            cwd=cwd,
            env=command_env(no_proxy=no_proxy),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform.startswith("win") else 0,
            start_new_session=not sys.platform.startswith("win"),
        )
        stdout, stderr = process.communicate(timeout=timeout)
        returncode = process.returncode
    except subprocess.TimeoutExpired:
        kill_process_tree(process)
        stdout = ""
        stderr = f"command timed out after {timeout}s"
        returncode = 1
    except FileNotFoundError:
        stdout = ""
        stderr = f"command not found: {cmd[0]}"
        returncode = 127

    if stdout:
        print(stdout.strip())
    if stderr:
        print(stderr.strip(), file=sys.stderr)
    if returncode != 0 and not check:
        print(f"[sync_newsnow] WARNING: command exited with code {returncode}")
    if check and returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(cmd)}")
    return returncode


def load_lock() -> dict:
    if not LOCK_FILE.exists():
        return {}
    return json.loads(LOCK_FILE.read_text(encoding="utf-8"))


def current_head(target: Path) -> str:
    if not (target / ".git").exists():
        return ""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=target,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def ensure_clean(target: Path) -> None:
    if not (target / ".git").exists():
        return
    status = subprocess.check_output(["git", "status", "--porcelain"], cwd=target, text=True)
    if status.strip():
        raise RuntimeError(
            "engine/newsnow has local changes. Commit/stash them inside the "
            "NewsNow sub-repository or remove the directory before syncing."
        )


def ensure_repo(target: Path, no_proxy: bool = False) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.mkdir(parents=True, exist_ok=True)
    if not (target / ".git").exists():
        print(f"[sync_newsnow] Initializing {REPO_URL} in {target}")
        run(git_cmd(["init"], no_proxy=no_proxy), cwd=target, check=True, no_proxy=no_proxy)

    remote = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=target,
        text=True,
        capture_output=True,
    )
    if remote.returncode != 0:
        run(git_cmd(["remote", "add", "origin", REPO_URL], no_proxy=no_proxy), cwd=target, check=True, no_proxy=no_proxy)
    elif remote.stdout.strip() != REPO_URL:
        run(git_cmd(["remote", "set-url", "origin", REPO_URL], no_proxy=no_proxy), cwd=target, check=True, no_proxy=no_proxy)


def sync_to_ref(
    target: Path,
    ref: str,
    dry_run: bool = False,
    allow_dirty_if_at_ref: bool = False,
    no_proxy: bool = False,
) -> None:
    ensure_repo(target, no_proxy=no_proxy)
    if allow_dirty_if_at_ref and current_head(target) == ref:
        print("[sync_newsnow] Already at locked ref; skip checkout to preserve embedded tree")
        return
    ensure_clean(target)
    print(f"[sync_newsnow] Target ref: {ref}")
    if dry_run:
        return
    if re.fullmatch(r"[0-9a-fA-F]{40}", ref):
        run(git_cmd(["fetch", "--no-tags", "--depth=1", "origin", ref], no_proxy=no_proxy), cwd=target, check=True, no_proxy=no_proxy)
        run(git_cmd(["checkout", "-B", "main", ref], no_proxy=no_proxy), cwd=target, check=True, no_proxy=no_proxy)
        return

    run(git_cmd(["fetch", "origin"], no_proxy=no_proxy), cwd=target, check=True, no_proxy=no_proxy)
    run(git_cmd(["checkout", ref], no_proxy=no_proxy), cwd=target, check=True, no_proxy=no_proxy)


def main() -> int:
    parser = argparse.ArgumentParser(description="Synchronize NewsNow")
    parser.add_argument("--check", action="store_true", help="Only print current/locked status")
    parser.add_argument("--update", choices=["lock", "latest"], default="lock")
    parser.add_argument("--ref", default="", help="Explicit git ref to checkout")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-proxy", action="store_true", help="Clear proxy variables for git clone/fetch")
    args = parser.parse_args()

    target = TARGET_DIR.resolve()
    lock = load_lock()
    locked_ref = lock.get("commit") or lock.get("ref") or "main"
    selected_ref = args.ref or ("origin/main" if args.update == "latest" else locked_ref)

    print(f"[sync_newsnow] target={target}")
    print(f"[sync_newsnow] locked_version={lock.get('version')} locked_ref={locked_ref}")
    if args.no_proxy:
        print("[sync_newsnow] proxy mode=disabled")

    if args.check:
        if (target / ".git").exists():
            run(["git", "rev-parse", "HEAD"], cwd=target)
            run(["git", "status", "--short"], cwd=target)
        else:
            print("[sync_newsnow] NewsNow is not cloned")
        return 0

    sync_to_ref(
        target,
        selected_ref,
        dry_run=args.dry_run,
        allow_dirty_if_at_ref=(not args.ref and args.update == "lock"),
        no_proxy=args.no_proxy,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
