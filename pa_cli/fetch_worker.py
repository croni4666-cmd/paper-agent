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
        operation = request.pop("_operation", "single")
        if operation == "batch_entry":
            from pathlib import Path
            from .fetch_batch import _fetch_one_entry_in_process
            request["out_dir"] = Path(request["out_dir"])
            result = _fetch_one_entry_in_process(**request).to_dict()
        elif operation == "single":
            from .fetch import _fetch_doi_in_process
            result = _fetch_doi_in_process(**request)
        else:
            raise ValueError("Unsupported worker operation")
    sys.stdout.buffer.write(json.dumps(result, ensure_ascii=False).encode("utf-8"))
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    main()
