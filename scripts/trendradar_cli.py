#!/usr/bin/env python
# coding=utf-8
"""JSON CLI for the Auto-Podcast TrendRadar adapter.

Electron calls this script so the main process does not need to import Python
modules directly. All logs from TrendRadar internals stay on stderr; stdout is
reserved for one JSON response.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _parse_version_tuple(value: str) -> tuple[int, ...]:
    return tuple(int(p) for p in re.findall(r"\d+", value or "0")[:3]) or (0,)


def _python_satisfies(requirement: str, version: str) -> bool:
    match = re.match(r">=\s*([0-9.]+)", requirement or "")
    if not match:
        return True
    return _parse_version_tuple(version) >= _parse_version_tuple(match.group(1))


def _managed_python() -> Path:
    if sys.platform == "win32":
        return REPO_ROOT / ".venv-trendradar" / "Scripts" / "python.exe"
    return REPO_ROOT / ".venv-trendradar" / "bin" / "python"


def _lock_requirement() -> str:
    lock_file = REPO_ROOT / "engine" / "trendradar.lock.json"
    if not lock_file.exists():
        return ""
    try:
        return json.loads(lock_file.read_text(encoding="utf-8")).get("python", "")
    except Exception:
        return ""


def _missing_runtime_modules() -> list[str]:
    required = {
        "feedparser": "feedparser",
        "litellm": "litellm",
        "json-repair": "json_repair",
        "fastmcp": "fastmcp",
    }
    return [
        package_name
        for package_name, module_name in required.items()
        if importlib.util.find_spec(module_name) is None
    ]


def _maybe_reexec_managed_python() -> None:
    managed = _managed_python()
    if not managed.exists():
        return
    current = Path(sys.executable).resolve()
    if current == managed.resolve():
        return
    current_version = ".".join(map(str, sys.version_info[:3]))
    requirement = _lock_requirement()
    version_blocked = bool(requirement and not _python_satisfies(requirement, current_version))
    dependency_blocked = bool(_missing_runtime_modules())
    if version_blocked or dependency_blocked:
        os.execv(str(managed), [str(managed), *sys.argv])


_maybe_reexec_managed_python()

from engine import bridge


def _read_payload() -> Dict[str, Any]:
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    return json.loads(raw)


def main() -> int:
    parser = argparse.ArgumentParser(description="Auto-Podcast TrendRadar adapter CLI")
    parser.add_argument("action", choices=[
        "status",
        "get-config",
        "save-config",
        "list-sources",
        "run-once",
        "get-latest",
        "get-topics",
        "check-update",
        "update-dependency",
    ])
    parser.add_argument("--user-data-dir", default=None)
    args = parser.parse_args()

    try:
        payload = _read_payload()
        if args.action == "status":
            result = bridge.get_status(args.user_data_dir)
        elif args.action == "get-config":
            result = {"success": True, "config": bridge.get_config_view(args.user_data_dir)}
        elif args.action == "save-config":
            result = {"success": True, "config": bridge.save_config_view(payload.get("config") or payload, args.user_data_dir)}
        elif args.action == "list-sources":
            result = {"success": True, "sources": bridge.list_sources(args.user_data_dir)}
        elif args.action == "run-once":
            result = bridge.run_once(payload.get("config") or payload, args.user_data_dir)
        elif args.action == "get-latest":
            result = bridge.get_latest(args.user_data_dir)
        elif args.action == "get-topics":
            result = bridge.get_topics(args.user_data_dir)
        elif args.action == "check-update":
            result = bridge.check_update()
        elif args.action == "update-dependency":
            result = bridge.update_dependency(
                ref=str(payload.get("ref") or "latest"),
                install_deps=bool(payload.get("installDeps")),
                dry_run=bool(payload.get("dryRun")),
            )
        else:
            raise ValueError(f"Unsupported action: {args.action}")
    except Exception as exc:
        result = {"success": False, "error": str(exc)}

    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("success", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
