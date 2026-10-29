"""SQLite backup and restore commands."""

import argparse
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings


def database_path() -> Path:
    if not settings.database_url.startswith("sqlite:///"):
        raise RuntimeError("The local backup utility supports SQLite only")
    return Path(settings.database_url.removeprefix("sqlite:///"))


def create_backup() -> str:
    source = database_path()
    if not source.exists():
        raise FileNotFoundError(f"SQLite database not found: {source}")
    destination_dir = Path(settings.backup_dir)
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"helpflow-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.db"
    source_connection = sqlite3.connect(source)
    target_connection = sqlite3.connect(destination)
    try:
        source_connection.backup(target_connection)
    finally:
        target_connection.close()
        source_connection.close()
    return str(destination)


def list_backups() -> list[str]:
    directory = Path(settings.backup_dir)
    directory.mkdir(parents=True, exist_ok=True)
    return [str(path) for path in sorted(directory.glob("helpflow-*.db"), reverse=True)]


def restore_backup(backup_file: str) -> str:
    source = Path(backup_file).resolve()
    target = database_path().resolve()
    if not source.exists() or source.suffix != ".db":
        raise FileNotFoundError("A valid .db backup file is required")
    with sqlite3.connect(source) as connection:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"Backup integrity check failed: {integrity}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return str(target)


def main():
    parser = argparse.ArgumentParser(description="HelpFlow SQLite backup utility")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("create")
    subparsers.add_parser("list")
    restore = subparsers.add_parser("restore")
    restore.add_argument("backup_file")
    args = parser.parse_args()
    if args.command == "create":
        print(create_backup())
    elif args.command == "list":
        print("\n".join(list_backups()) or "No backups found")
    else:
        print(restore_backup(args.backup_file))


if __name__ == "__main__":
    main()
