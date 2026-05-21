from __future__ import annotations

import sys

from whitesnout.compress import compress_directory


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] in ("--help", "-h"):
        print("Usage: python -m whitesnout compress <directory>")
        sys.exit(0)

    cmd = args[0]
    if cmd == "compress":
        if len(args) < 2:
            print("Usage: python -m whitesnout compress <directory>")
            sys.exit(1)
        compress_directory(args[1])
    else:
        print(f"Unknown command: {cmd}")
        print("Usage: python -m whitesnout compress <directory>")
        sys.exit(1)
