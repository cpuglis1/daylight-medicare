#!/usr/bin/env python3
"""Install Daylight's index-only checks without replacing existing Git hooks."""
from pathlib import Path
import argparse
import os
import subprocess


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


def install(root):
    root = Path(root).resolve(strict=True)
    if Path(git(root, "rev-parse", "--show-toplevel")).resolve() != root:
        raise ValueError("Use the repository root")
    configured = subprocess.run(["git", "-C", str(root), "config", "--get", "core.hooksPath"],
                                capture_output=True, text=True)
    if configured.returncode not in (0, 1):
        raise ValueError("Could not inspect the existing hook configuration")
    existing = configured.stdout.strip()
    if existing and existing != ".githooks":
        raise ValueError("An existing hooksPath must be integrated manually; nothing changed")
    if not existing:
        directory = Path(git(root, "rev-parse", "--git-path", "hooks"))
        if not directory.is_absolute():
            directory = root / directory
        if directory.exists() and any(p.is_file() and os.access(p, os.X_OK)
                                      and not p.name.endswith(".sample")
                                      for p in directory.iterdir()):
            raise ValueError("Existing executable hooks must be integrated manually; nothing changed")
    for name in (".githooks/pre-commit", "tools/baseline_checks.py", "tools/project_readiness.py"):
        target = root / name
        if not target.is_file() or target.is_symlink():
            raise ValueError("Required regular hook/checker files are missing; nothing changed")
    if not os.access(root / ".githooks/pre-commit", os.X_OK):
        raise ValueError("The pre-commit hook must be executable; nothing changed")
    git(root, "config", "--local", "core.hooksPath", ".githooks")
    return "Installed .githooks: staged secret, publication and integrity checks; no files staged."


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        print(install(args.root))
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(str(error) if isinstance(error, ValueError) else "Hook installation failed; inspect Git access.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
