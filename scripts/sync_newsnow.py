#!/usr/bin/env python3
"""Synchronize the NewsNow source service into engine/newsnow.

NewsNow is kept as an external data-source service for TrendRadar. This script
fetches/checks out the source tree. Dependency install and runtime startup are
explicit steps handled by scripts/newsnow_runtime.js.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import signal
import subprocess
import sys
from pathlib import Path

DEFAULT_REPO_URL = "https://github.com/ourongxing/newsnow.git"
ROOT_DIR = Path(__file__).resolve().parent.parent
TARGET_DIR = ROOT_DIR / "engine" / "newsnow"
LOCK_FILE = ROOT_DIR / "engine" / "newsnow.lock.json"
OVERLAY_STATE_NAME = ".auto-podcast-overlay.json"
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


def repo_url(lock: dict) -> str:
    return str(lock.get("repo") or DEFAULT_REPO_URL)


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


def ensure_repo(target: Path, lock: dict, no_proxy: bool = False) -> None:
    url = repo_url(lock)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.mkdir(parents=True, exist_ok=True)
    if not (target / ".git").exists():
        print(f"[sync_newsnow] Initializing {url} in {target}")
        run(git_cmd(["init"], no_proxy=no_proxy), cwd=target, check=True, no_proxy=no_proxy)

    remote = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=target,
        text=True,
        capture_output=True,
    )
    if remote.returncode != 0:
        run(git_cmd(["remote", "add", "origin", url], no_proxy=no_proxy), cwd=target, check=True, no_proxy=no_proxy)
    elif remote.stdout.strip() != url:
        run(git_cmd(["remote", "set-url", "origin", url], no_proxy=no_proxy), cwd=target, check=True, no_proxy=no_proxy)


def rel(path: Path) -> str:
    return path.as_posix()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def overlay_manifests(lock: dict) -> list[tuple[dict, Path]]:
    manifests: list[tuple[dict, Path]] = []
    for overlay in lock.get("overlays") or []:
        overlay_path = ROOT_DIR / str(overlay.get("path", ""))
        manifest_path = overlay_path / "manifest.json"
        if not manifest_path.exists():
            raise RuntimeError(f"NewsNow overlay manifest not found: {manifest_path}")
        manifest = read_json(manifest_path)
        manifest.setdefault("id", overlay.get("id") or overlay_path.name)
        manifest.setdefault("version", overlay.get("version") or "")
        manifests.append((manifest, overlay_path))
    return manifests


def git_status_lines(target: Path) -> list[str]:
    status = subprocess.check_output(["git", "status", "--porcelain"], cwd=target, text=True)
    return [line for line in status.splitlines() if line.strip()]


def status_path(line: str) -> str:
    path = line[3:].strip()
    if " -> " in path:
        path = path.rsplit(" -> ", 1)[1]
    return path.replace("\\", "/")


def git_head_text(target: Path, rel_path: str) -> str | None:
    result = subprocess.run(
        ["git", "show", f"HEAD:{rel_path}"],
        cwd=target,
        capture_output=True,
    )
    return result.stdout.decode("utf-8", errors="replace") if result.returncode == 0 else None


def normalize_text(value: str) -> str:
    return value.replace("\r\n", "\n")


def overlay_patches_by_target(lock: dict) -> dict[str, list[dict]]:
    by_target: dict[str, list[dict]] = {}
    for manifest, _overlay_dir in overlay_manifests(lock):
        for patch in manifest.get("text_patches") or []:
            target = str(patch.get("target") or "").replace("\\", "/")
            if target:
                by_target.setdefault(target, []).append(patch)
    return by_target


def apply_overlay_patch_to_text(text: str, patch: dict) -> str:
    marker = normalize_text(str(patch["marker"]))
    insert = normalize_text("\n".join(str(line) for line in patch.get("insert_lines") or []))
    position = str(patch.get("position") or "after")

    if insert in text:
        return text
    if marker not in text:
        return text
    if position == "before":
        return text.replace(marker, f"{insert}\n{marker}", 1)
    return text.replace(marker, f"{marker}\n{insert}", 1)


def strip_overlay_insert(text: str, patch: dict) -> str:
    insert = normalize_text("\n".join(str(line) for line in patch.get("insert_lines") or []))
    if f"{insert}\n" in text:
        return text.replace(f"{insert}\n", "", 1)
    if f"\n{insert}" in text:
        return text.replace(f"\n{insert}", "", 1)
    return text


def is_overlay_patch_only_dirty(target: Path, rel_path: str, patches: list[dict]) -> bool:
    base = git_head_text(target, rel_path)
    path = target / rel_path
    if base is None or not path.exists():
        return False

    current = normalize_text(path.read_text(encoding="utf-8"))
    expected = normalize_text(base)
    for patch in patches:
        expected = apply_overlay_patch_to_text(expected, patch)
    if current == expected:
        return True

    stripped = current
    for patch in patches:
        stripped = strip_overlay_insert(stripped, patch)
    return stripped == normalize_text(base)


def ensure_clean(target: Path, lock: dict | None = None, allow_managed: bool = False) -> None:
    if not (target / ".git").exists():
        return

    lines = git_status_lines(target)
    if not lines:
        return

    unknown = lines
    if allow_managed and lock is not None:
        generated_paths = {str(path).replace("\\", "/") for path in (lock.get("generated_paths") or [])}
        patch_targets = overlay_patches_by_target(lock)
        unknown = []
        for line in lines:
            path = status_path(line)
            if path in generated_paths:
                continue
            if path in patch_targets and is_overlay_patch_only_dirty(target, path, patch_targets[path]):
                continue
            unknown.append(line)

    if unknown:
        details = "\n".join(f"  {line}" for line in unknown)
        raise RuntimeError(
            "engine/newsnow has local changes outside Auto-Podcast managed overlay/build outputs. "
            "Commit/stash them inside the NewsNow sub-repository or remove the directory before syncing.\n"
            f"{details}"
        )


def update_git_exclude(target: Path, paths: list[str]) -> None:
    exclude = target / ".git" / "info" / "exclude"
    if not exclude.exists():
        return
    existing = exclude.read_text(encoding="utf-8", errors="ignore")
    additions = [p for p in paths if p and p not in existing]
    if not additions:
        return
    with exclude.open("a", encoding="utf-8") as handle:
        handle.write("\n# Auto-Podcast NewsNow overlay\n")
        for path in additions:
            handle.write(f"{path}\n")


def copy_overlay_file(overlay_dir: Path, target: Path, entry: dict, dry_run: bool) -> dict:
    source_rel = str(entry["source"])
    target_rel = str(entry["target"])
    source = overlay_dir / source_rel
    destination = target / target_rel
    if not source.exists():
        raise RuntimeError(f"NewsNow overlay source file not found: {source}")

    source_text = source.read_text(encoding="utf-8")
    previous = destination.read_text(encoding="utf-8") if destination.exists() else None
    overwrite = bool(entry.get("overwrite", False))
    if previous is not None and previous != source_text and not overwrite:
        raise RuntimeError(f"NewsNow overlay target exists and overwrite=false: {target_rel}")

    if not dry_run:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(source_text, encoding="utf-8")

    return {
        "type": "file",
        "source": source_rel,
        "target": target_rel,
        "changed": previous != source_text,
    }


def apply_text_patch(target: Path, patch: dict, dry_run: bool) -> dict:
    target_rel = str(patch["target"])
    path = target / target_rel
    if not path.exists():
        raise RuntimeError(f"NewsNow overlay patch target not found: {target_rel}")

    marker = str(patch["marker"])
    position = str(patch.get("position") or "after")
    insert = "\n".join(str(line) for line in patch.get("insert_lines") or [])
    if not insert:
        raise RuntimeError(f"NewsNow overlay patch has empty insert_lines: {patch.get('id')}")

    text = path.read_text(encoding="utf-8")
    normalized_text = text.replace("\r\n", "\n")
    normalized_insert = insert.replace("\r\n", "\n")
    if normalized_insert in normalized_text:
        return {
            "type": "text_patch",
            "id": patch.get("id"),
            "target": target_rel,
            "changed": False,
        }
    if marker not in text:
        raise RuntimeError(f"NewsNow overlay patch marker not found in {target_rel}: {marker}")

    if position == "before":
        next_text = text.replace(marker, f"{insert}\n{marker}", 1)
    elif position == "after":
        next_text = text.replace(marker, f"{marker}\n{insert}", 1)
    else:
        raise RuntimeError(f"Unsupported overlay patch position: {position}")

    if not dry_run:
        path.write_text(next_text, encoding="utf-8")

    return {
        "type": "text_patch",
        "id": patch.get("id"),
        "target": target_rel,
        "changed": True,
    }


def apply_overlays(target: Path, lock: dict, dry_run: bool = False) -> dict:
    operations: list[dict] = []
    ignored_paths = [OVERLAY_STATE_NAME]
    applied_overlays: list[dict] = []

    for manifest, overlay_dir in overlay_manifests(lock):
        overlay_id = manifest.get("id") or overlay_dir.name
        print(f"[sync_newsnow] Applying overlay: {overlay_id}")

        for entry in manifest.get("files") or []:
            operations.append(copy_overlay_file(overlay_dir, target, entry, dry_run))
            ignored_paths.append(str(entry["target"]))

        for patch in manifest.get("text_patches") or []:
            operations.append(apply_text_patch(target, patch, dry_run))

        applied_overlays.append({
            "id": overlay_id,
            "version": manifest.get("version", ""),
            "path": rel(overlay_dir.relative_to(ROOT_DIR)),
        })

    state = {
        "applied": True,
        "applied_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "locked_commit": lock.get("commit") or "",
        "overlays": applied_overlays,
        "operations": operations,
    }

    if not dry_run:
        update_git_exclude(target, ignored_paths)
        (target / OVERLAY_STATE_NAME).write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    return state


def sync_to_ref(
    target: Path,
    lock: dict,
    ref: str,
    dry_run: bool = False,
    allow_dirty_if_at_ref: bool = False,
    no_proxy: bool = False,
) -> None:
    ensure_repo(target, lock, no_proxy=no_proxy)
    if allow_dirty_if_at_ref and current_head(target) == ref:
        ensure_clean(target, lock, allow_managed=True)
        print("[sync_newsnow] Already at locked ref; skip checkout to preserve embedded tree")
        return
    ensure_clean(target, lock)
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
            state_file = target / OVERLAY_STATE_NAME
            if state_file.exists():
                print(state_file.read_text(encoding="utf-8"))
            else:
                print("[sync_newsnow] NewsNow overlay is not applied")
        else:
            print("[sync_newsnow] NewsNow is not cloned")
        return 0

    sync_to_ref(
        target,
        lock,
        selected_ref,
        dry_run=args.dry_run,
        allow_dirty_if_at_ref=(not args.ref and args.update == "lock"),
        no_proxy=args.no_proxy,
    )
    apply_overlays(target, lock, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
