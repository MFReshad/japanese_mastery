#!/usr/bin/env python
import argparse
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1] / "backend"))

from app.db.session import SessionLocal  # noqa: E402
from app.services.importer import import_directory  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Import Japanese Mastery JSON datasets.")
    parser.add_argument("directory", type=Path)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--commit", action="store_true")
    args = parser.parse_args()
    with SessionLocal() as db:
        result = import_directory(db, args.directory, dry_run=args.dry_run)
    for name, stats in result.items():
        if name == "summary":
            continue
        print(f"{name}: WOULD INSERT={stats['would_insert']} WOULD UPDATE={stats['would_update']} "
              f"WOULD SKIP={stats['would_skip']} CONFLICT={stats['conflict_count']} ERROR={len(stats['errors'])}")
        for error in stats["errors"]:
            print(f"  error: {error}")
    summary = result["summary"]
    print(f"summary: dry_run={summary['dry_run']} rolled_back={summary['rolled_back']} fatal_error={summary['fatal_error']}")

    if summary["fatal_error"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
