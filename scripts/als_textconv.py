"""Show an Ableton .als as XML so git can diff it.

A .als is gzipped XML, so git sees one opaque blob and every save looks like
"binary files differ". This filter decompresses it on the fly for diffing
only; nothing on disk is touched and git still stores the original bytes.

Enable it once per clone (the .gitattributes entry is already committed):

    git config diff.als.textconv "python scripts/als_textconv.py"

Then `git diff` on a Live Set shows which tracks, devices and parameters
actually changed. Borrowed idea: mgarriss/guard-live-set.
"""

import gzip
import sys
from pathlib import Path


def als_to_xml(path: Path) -> str:
    raw = path.read_bytes()
    if raw[:2] == b"\x1f\x8b":  # gzip magic
        raw = gzip.decompress(raw)
    return raw.decode("utf-8", "replace")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"usage: {Path(argv[0]).name} <file.als>", file=sys.stderr)
        return 2
    path = Path(argv[1])
    if not path.is_file():
        print(f"not a file: {path}", file=sys.stderr)
        return 2
    try:
        sys.stdout.write(als_to_xml(path))
    except BrokenPipeError:
        # git pipes this into a pager that may close early; not an error.
        sys.stderr.close()
        return 0
    except OSError as exc:
        print(f"could not read {path}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
