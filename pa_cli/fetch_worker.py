"""Private stdin/stdout protocol for the supervised single-fetch process."""
import contextlib
import json
import os
import sys
import time


def main():
    # No provider import/work before the parent has attached containment and
    # supplied the request. Keep provider output out of the result protocol.
    request = json.loads(sys.stdin.buffer.read())
    from .fetch_trace import configure, emit
    deadline = request.pop('_deadline', None)
    configure(request.pop('_trace_path', None))
    emit('worker', 'started')
    from . import fetch_deadline
    fetch_deadline._IN_FETCH_WORKER = True
    with open(os.devnull, "w") as sink, contextlib.redirect_stdout(sink):
        operation = request.pop("_operation", "single")
        if operation == "validate_pdf":
            from .pdf_validation import validation_worker
            result = validation_worker(**request)
        elif operation == "batch_entry":
            from pathlib import Path
            from .fetch_batch import _fetch_one_entry_in_process
            request["out_dir"] = Path(request["out_dir"])
            result = _fetch_one_entry_in_process(**request).to_dict()
        elif operation == "cache_write":
            from pathlib import Path
            from .cache import cache_put
            path = Path(request.pop('path'))
            cache_put(body=path.read_bytes(), **request)
            result = {'cache_written': True}
        elif operation == "single":
            from .fetch import _fetch_doi_in_process
            if deadline is not None:
                request['max_total_sec'] = deadline - time.monotonic()
            result = _fetch_doi_in_process(**request)
        else:
            raise ValueError("Unsupported worker operation")
    emit("worker", "completed")
    sys.stdout.buffer.write(json.dumps(result, ensure_ascii=False).encode("utf-8"))
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    main()
