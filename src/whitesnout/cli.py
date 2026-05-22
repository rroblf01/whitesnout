from __future__ import annotations

import argparse
import sys
from pathlib import Path

from whitesnout.compress import compress_directory


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="whitesnout",
        description="WhiteSnout command-line tools",
    )
    sub = parser.add_subparsers(dest="command")

    _add_compress(sub)
    _add_serve(sub)
    _add_validate(sub)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "compress":
        compress_directory(
            args.directory,
            force=args.force,
            include=args.include,
            exclude=args.exclude,
            jobs=args.jobs,
            quiet=args.quiet,
        )
    elif args.command == "serve":
        _run_serve(args)
    elif args.command == "validate":
        sys.exit(_run_validate(args))


def _add_compress(sub: argparse._SubParsersAction) -> None:
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


def _add_serve(sub: argparse._SubParsersAction) -> None:
    sv = sub.add_parser(
        "serve",
        help="Launch a uvicorn-backed standalone server",
    )
    sv.add_argument("directory", help="Directory to serve")
    sv.add_argument(
        "--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)"
    )
    sv.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    sv.add_argument(
        "--workers",
        type=int,
        default=1,
        help="uvicorn worker count (default: 1). Forces single-process when 1.",
    )
    sv.add_argument(
        "--health-check-path",
        default=None,
        metavar="PATH",
        help="Expose a 200 OK health endpoint at this path (e.g. /healthz)",
    )
    sv.add_argument(
        "--request-id-header",
        default=None,
        metavar="HEADER",
        help="Echo / generate this header on every response (e.g. X-Request-ID)",
    )
    sv.add_argument(
        "--log-level",
        default="info",
        choices=("critical", "error", "warning", "info", "debug", "trace"),
        help="uvicorn log level",
    )


def _add_validate(sub: argparse._SubParsersAction) -> None:
    vl = sub.add_parser(
        "validate",
        help="Pre-flight checks: directory, manifest, brotli availability",
    )
    vl.add_argument("directory", help="Directory to validate")
    vl.add_argument(
        "--manifest",
        default=None,
        metavar="PATH",
        help="Path to a manifest file to load and parse",
    )
    vl.add_argument(
        "--require-brotli",
        action="store_true",
        help="Exit non-zero if the brotli package is not importable",
    )
    vl.add_argument(
        "--require-rust",
        action="store_true",
        help="Exit non-zero if the Rust extension is not available",
    )


def _run_serve(args: argparse.Namespace) -> None:
    try:
        import uvicorn
    except ImportError:
        print(
            "Error: `uvicorn` is required for `whitesnout serve`. "
            "Install with: pip install 'uvicorn[standard]'",
            file=sys.stderr,
        )
        sys.exit(1)

    from whitesnout import WhiteSnout

    directory = args.directory
    if not Path(directory).is_dir():
        print(f"Error: '{directory}' is not a directory", file=sys.stderr)
        sys.exit(1)

    app = WhiteSnout(
        directory=directory,
        health_check_path=args.health_check_path,
        request_id_header=args.request_id_header,
    )

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        workers=args.workers if args.workers > 1 else None,
        log_level=args.log_level,
    )


def _run_validate(args: argparse.Namespace) -> int:
    rc = 0
    directory = Path(args.directory)
    if not directory.is_dir():
        print(f"FAIL  directory: '{args.directory}' does not exist")
        return 1
    print(f"OK    directory: {directory.resolve()}")

    files = sum(1 for _ in directory.rglob("*") if _.is_file())
    print(f"OK    files: {files} regular files under directory")

    try:
        import brotli  # noqa: F401

        print("OK    brotli: importable")
    except ImportError:
        msg = "WARN  brotli: not installed (install whitesnout[compress])"
        if args.require_brotli:
            print("FAIL " + msg[4:])
            rc = 1
        else:
            print(msg)

    try:
        from whitesnout import _rs  # noqa: F401

        print("OK    rust extension: loaded")
    except ImportError:
        msg = "WARN  rust extension: not available (falling back to pure-Python path)"
        if args.require_rust:
            print("FAIL " + msg[4:])
            rc = 1
        else:
            print(msg)

    if args.manifest is not None:
        from whitesnout.manifest import load_manifest

        try:
            paths = load_manifest(args.manifest)
        except Exception as e:
            print(f"FAIL  manifest: {args.manifest} could not be parsed: {e}")
            return 1
        print(f"OK    manifest: {args.manifest} ({len(paths)} entries)")

    return rc
