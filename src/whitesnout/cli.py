from __future__ import annotations

import argparse
import sys

from whitesnout.compress import compress_directory


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="whitesnout",
        description="WhiteSnout command-line tools",
    )
    sub = parser.add_subparsers(dest="command")

    cp = sub.add_parser(
        "compress",
        help="Pre-compress files in a directory into .gz/.br siblings",
    )
    cp.add_argument("directory", help="Directory to compress")
    cp.add_argument(
        "--force",
        action="store_true",
        help="Recompress files even when .gz/.br is newer than the source",
    )
    cp.add_argument(
        "--include",
        action="append",
        default=[],
        metavar="GLOB",
        help="Only compress files matching this glob (relative to <directory>). "
        "Repeatable.",
    )
    cp.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="GLOB",
        help="Skip files matching this glob. Repeatable.",
    )
    cp.add_argument(
        "--jobs",
        "-j",
        type=int,
        default=None,
        metavar="N",
        help="Worker processes (default: CPU count)",
    )
    cp.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress per-run summary output",
    )

    args = parser.parse_args()

    if args.command is None or args.command not in {"compress"}:
        parser.print_help()
        sys.exit(0 if args.command is None else 1)

    if args.command == "compress":
        compress_directory(
            args.directory,
            force=args.force,
            include=args.include,
            exclude=args.exclude,
            jobs=args.jobs,
            quiet=args.quiet,
        )
