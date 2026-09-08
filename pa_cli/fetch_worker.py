"""Private stdin/stdout protocol for the supervised single-fetch process."""
import contextlib
import json
import os
import sys


def main():
    # No provider import/work before the parent has attached containment and
    # supplied the request. Keep provider output out of the result protocol.
    request = json.loads(sys.stdin.buffer.read())
    with open(os.devnull, "w") as sink, contextlib.redirect_stdout(sink):
        from .fetch import _fetch_doi_in_process
        result = _fetch_doi_in_process(**request)
    sys.stdout.buffer.write(json.dumps(result, ensure_ascii=False).encode("utf-8"))
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    main()
