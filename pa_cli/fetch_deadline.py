"""Process supervision for single-paper retrieval.

Windows uses a kill-on-close Job Object; POSIX uses a dedicated process group.
The worker waits for stdin until containment is established by its parent.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


# Set only by our private worker after containment has been established.
_IN_FETCH_WORKER = False


class _WindowsJob:
    def __init__(self, memory_mb=None):
        import ctypes as c
        from ctypes import wintypes as w

        class Basic(c.Structure):
            _fields_ = [("process_time", c.c_int64), ("job_time", c.c_int64),
                        ("flags", w.DWORD), ("min_ws", c.c_size_t),
                        ("max_ws", c.c_size_t), ("active", w.DWORD),
                        ("affinity", c.c_size_t), ("priority", w.DWORD),
                        ("scheduling", w.DWORD)]

        class Extended(c.Structure):
            _fields_ = [("basic", Basic), ("io", c.c_uint64 * 6),
                        ("process_memory", c.c_size_t), ("job_memory", c.c_size_t),
                        ("peak_process", c.c_size_t), ("peak_job", c.c_size_t)]

        self.api = c.WinDLL("kernel32", use_last_error=True)
        for name, args, result in (
            ("CreateJobObjectW", [c.c_void_p, w.LPCWSTR], w.HANDLE),
            ("SetInformationJobObject", [w.HANDLE, c.c_int, c.c_void_p, w.DWORD], w.BOOL),
            ("AssignProcessToJobObject", [w.HANDLE, w.HANDLE], w.BOOL),
            ("OpenProcess", [w.DWORD, w.BOOL, w.DWORD], w.HANDLE),
            ("CloseHandle", [w.HANDLE], w.BOOL),
        ):
            fn = getattr(self.api, name)
            fn.argtypes, fn.restype = args, result
        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle:
            raise OSError("Cannot create download process containment")
        info = Extended()
        info.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if memory_mb is not None:
            info.basic.flags |= 0x200  # JOB_OBJECT_LIMIT_JOB_MEMORY
            info.job_memory = int(memory_mb * 1024 * 1024)
        if not self.api.SetInformationJobObject(self.handle, 9, c.byref(info), c.sizeof(info)):
            self.close()
            raise OSError("Cannot configure download process containment")

    def assign(self, pid):
        handle = self.api.OpenProcess(0x0101, False, pid)  # SET_QUOTA | TERMINATE
        if not handle:
            raise OSError("Cannot access download worker")
        try:
            if not self.api.AssignProcessToJobObject(self.handle, handle):
                raise OSError("Cannot contain download worker")
        finally:
            self.api.CloseHandle(handle)

    def close(self):
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None


def _failure(code, started):
    return {"error": code, "saved_as": None, "final_status": "ALL_FAIL",
            "elapsed_sec": round(time.monotonic() - started, 3),
            "hint": "Increase max_total_sec or retry" if code == "fetch_timeout"
                    else "Download worker could not complete; check the local environment",
            "_wrapper_notes": {"max_total_sec_supported": True}}


def run_fetch(request, seconds, *, _command=None, _memory_mb=None):
    """Run one private worker; return sanitized failures and always reap it.

    No user inputs are placed on the command line. POSIX children deliberately
    detaching into another session are outside process-group containment.
    """
    started = time.monotonic()
    try:
        valid = (not isinstance(seconds, bool) and isinstance(seconds, (int, float))
                 and math.isfinite(seconds) and seconds > 0)
    except OverflowError:
        valid = False
    if not valid:
        return _failure("fetch_invalid_timeout", started)
    process = job = None
    # A nested PDF parser must stay in the retrieval group: if its supervising
    # worker is killed, the outer supervisor must still be able to reap it.
    shared_group = os.name != 'nt' and _IN_FETCH_WORKER and _memory_mb is not None
    try:
        payload = json.dumps(request).encode("utf-8")
        if os.name == "nt":
            job = _WindowsJob(_memory_mb)
        command = _command or [sys.executable, "-c",
                              "import sys; sys.path.insert(0, sys.argv[1]); "
                              "from pa_cli.fetch_worker import main; main()",
                              str(Path(__file__).resolve().parent.parent)]
        if _memory_mb is not None and os.name != 'nt':
            command = [sys.executable, '-c',
                       'import resource,os,sys; n=int(sys.argv[1]); '
                       'resource.setrlimit(resource.RLIMIT_AS,(n,n)); '
                       'os.execv(sys.argv[2],sys.argv[2:])',
                       str(int(_memory_mb * 1024 * 1024)), *command]
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            start_new_session=os.name != "nt" and not shared_group,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        if job:
            job.assign(process.pid)
        remaining = seconds - (time.monotonic() - started)
        if remaining <= 0:
            return _failure("fetch_timeout", started)
        output, _ = process.communicate(payload, timeout=remaining)
        if time.monotonic() - started > seconds:
            return _failure("fetch_timeout", started)
        if process.returncode:
            return _failure("fetch_worker_failed", started)
        result = json.loads(output)
        if not isinstance(result, dict):
            return _failure("fetch_worker_failed", started)
        result.setdefault("_wrapper_notes", {})["max_total_sec_supported"] = True
        result["elapsed_sec"] = round(time.monotonic() - started, 3)
        return result
    except subprocess.TimeoutExpired:
        return _failure("fetch_timeout", started)
    except (OSError, ValueError, TypeError):
        return _failure("fetch_worker_failed", started)
    finally:
        # Kill descendants even if their direct parent already exited.
        if job:
            job.close()
        elif process and not shared_group:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if process:
            if process.poll() is None:
                process.kill()
            process.wait()
            for stream in (process.stdin, process.stdout):
                if stream:
                    stream.close()
