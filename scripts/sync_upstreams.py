#!/usr/bin/env python3
"""Synchronize selected image directories from upstream atlas repositories."""

from __future__ import annotations

import argparse
import filecmp
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "sync_sources.json"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
IGNORED_NAMES = {".DS_Store"}


class SyncError(RuntimeError):
    """Raised when configuration or upstream data is unsafe to use."""


@dataclass(frozen=True)
class Mapping:
    source: str
    destination: str


@dataclass(frozen=True)
class Repository:
    name: str
    url: str
    branch: str
    mappings: tuple[Mapping, ...]


@dataclass
class Summary:
    added: int = 0
    updated: int = 0
    deleted: int = 0

    @property
    def changed(self) -> bool:
        return bool(self.added or self.updated or self.deleted)

    def merge(self, other: "Summary") -> None:
        self.added += other.added
        self.updated += other.updated
        self.deleted += other.deleted


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="mapping configuration (default: %(default)s)",
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        help="use existing repositories under this directory instead of cloning",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=DEFAULT_CONFIG.parent,
        help="destination repository root (default: target repository)",
    )
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        metavar="REPOSITORY",
        help="only sync the named repository; may be repeated",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="show changes without writing files",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="show changes and exit 1 when synchronization is needed",
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="delete managed image files missing upstream (off by default)",
    )
    parser.add_argument(
        "--skip-metadata",
        action="store_true",
        help="do not run cal_md5.py after writing image changes",
    )
    return parser.parse_args()


def safe_child(root: Path, relative: str, label: str) -> Path:
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise SyncError(f"{label} escapes its repository root: {relative}") from exc
    return candidate


def require_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SyncError(f"{label} must be a non-empty string")
    return value


def load_config(path: Path) -> tuple[Repository, ...]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SyncError(f"cannot read configuration {path}: {exc}") from exc

    entries = raw.get("repositories") if isinstance(raw, dict) else None
    if not isinstance(entries, list) or not entries:
        raise SyncError("configuration must contain a non-empty repositories list")

    repositories: list[Repository] = []
    names: set[str] = set()
    destinations: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise SyncError(f"repositories[{index}] must be an object")
        name = require_string(entry.get("name"), f"repositories[{index}].name")
        if name in names:
            raise SyncError(f"duplicate repository name: {name}")
        names.add(name)

        raw_mappings = entry.get("mappings")
        if not isinstance(raw_mappings, list) or not raw_mappings:
            raise SyncError(f"repository {name} must contain mappings")
        mappings: list[Mapping] = []
        for map_index, item in enumerate(raw_mappings):
            if not isinstance(item, dict):
                raise SyncError(f"{name}.mappings[{map_index}] must be an object")
            source = require_string(item.get("source"), f"{name}.source")
            destination = require_string(item.get("destination"), f"{name}.destination")
            normalized_destination = Path(destination).as_posix().rstrip("/")
            if normalized_destination in destinations:
                raise SyncError(f"destination is managed more than once: {destination}")
            destinations.add(normalized_destination)
            mappings.append(Mapping(source=source, destination=destination))

        repositories.append(
            Repository(
                name=name,
                url=require_string(entry.get("url"), f"{name}.url"),
                branch=require_string(entry.get("branch"), f"{name}.branch"),
                mappings=tuple(mappings),
            )
        )
    return tuple(repositories)


def clone_repository(repository: Repository, checkout_root: Path) -> Path:
    destination = checkout_root / repository.name
    command = [
        "git",
        "clone",
        "--depth=1",
        "--single-branch",
        "--filter=blob:none",
        "--sparse",
        "--branch",
        repository.branch,
        repository.url,
        os.fspath(destination),
    ]
    print(f"Fetching {repository.name} ({repository.branch})", flush=True)
    try:
        subprocess.run(command, check=True)
        subprocess.run(
            [
                "git",
                "-C",
                os.fspath(destination),
                "sparse-checkout",
                "set",
                "--cone",
                *(mapping.source for mapping in repository.mappings),
            ],
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SyncError(f"failed to fetch {repository.name}") from exc
    return destination


def image_files(directory: Path) -> dict[Path, Path]:
    result: dict[Path, Path] = {}
    for path in directory.rglob("*"):
        if (
            not path.is_file()
            or path.name in IGNORED_NAMES
            or path.suffix.lower() not in IMAGE_SUFFIXES
        ):
            continue
        resolved = path.resolve()
        try:
            resolved.relative_to(directory.resolve())
        except ValueError as exc:
            raise SyncError(f"source file escapes its mapped directory: {path}") from exc
        result[path.relative_to(directory)] = path
    return result


def atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.sync-{os.getpid()}")
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def sync_mapping(
    source: Path,
    destination: Path,
    *,
    dry_run: bool,
    delete: bool,
) -> Summary:
    if not source.is_dir():
        raise SyncError(f"mapped source directory does not exist: {source}")
    if destination.exists() and not destination.is_dir():
        raise SyncError(f"mapped destination is not a directory: {destination}")

    source_files = image_files(source)
    if not source_files:
        raise SyncError(f"mapped source contains no supported images: {source}")
    destination_files = image_files(destination) if destination.exists() else {}
    summary = Summary()

    for relative, source_file in sorted(source_files.items(), key=lambda item: str(item[0])):
        destination_file = destination / relative
        if not destination_file.exists():
            action = "ADD"
            summary.added += 1
        elif not filecmp.cmp(source_file, destination_file, shallow=False):
            action = "UPDATE"
            summary.updated += 1
        else:
            continue
        print(f"  {action:6} {destination_file}")
        if not dry_run:
            atomic_copy(source_file, destination_file)

    if delete:
        for relative, destination_file in sorted(
            destination_files.items(), key=lambda item: str(item[0])
        ):
            if relative in source_files:
                continue
            print(f"  DELETE {destination_file}")
            summary.deleted += 1
            if not dry_run:
                destination_file.unlink()

    return summary


def run_metadata(repo_root: Path) -> None:
    script = repo_root / "cal_md5.py"
    if not script.is_file():
        raise SyncError(f"metadata generator does not exist: {script}")
    print("Refreshing md5.json and alias.json")
    try:
        subprocess.run([sys.executable, os.fspath(script)], cwd=repo_root, check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SyncError("metadata generation failed") from exc


def select_repositories(
    repositories: Iterable[Repository], selected_names: list[str]
) -> tuple[Repository, ...]:
    repositories = tuple(repositories)
    if not selected_names:
        return repositories
    selected = set(selected_names)
    known = {repository.name for repository in repositories}
    unknown = selected - known
    if unknown:
        raise SyncError(f"unknown repositories: {', '.join(sorted(unknown))}")
    return tuple(repository for repository in repositories if repository.name in selected)


def main() -> int:
    args = parse_args()
    dry_run = args.dry_run or args.check
    try:
        config_path = args.config.resolve()
        repo_root = args.repo_root.resolve()
        repositories = select_repositories(load_config(config_path), args.only)
        source_root = args.source_root.resolve() if args.source_root else None
        total = Summary()

        with tempfile.TemporaryDirectory(prefix="atlas-sync-") as temporary:
            checkout_root = Path(temporary)
            for repository in repositories:
                if source_root:
                    upstream_root = safe_child(
                        source_root, repository.name, f"local source for {repository.name}"
                    )
                    if not upstream_root.is_dir():
                        raise SyncError(f"local repository does not exist: {upstream_root}")
                    print(f"Using local {repository.name}: {upstream_root}")
                else:
                    upstream_root = clone_repository(repository, checkout_root)

                for mapping in repository.mappings:
                    source = safe_child(upstream_root, mapping.source, "mapping source")
                    destination = safe_child(repo_root, mapping.destination, "mapping destination")
                    print(f"Syncing {repository.name}:{mapping.source} -> {mapping.destination}")
                    total.merge(
                        sync_mapping(
                            source,
                            destination,
                            dry_run=dry_run,
                            delete=args.delete,
                        )
                    )

        if total.changed and not dry_run and not args.skip_metadata:
            run_metadata(repo_root)

        mode = "would change" if dry_run else "changed"
        print(
            f"Done: {mode} {total.added} added, {total.updated} updated, "
            f"{total.deleted} deleted"
        )
        return 1 if args.check and total.changed else 0
    except SyncError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
