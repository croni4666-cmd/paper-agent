"""Read-only process-instance identity for local gateway reservations.

None means insufficient OS evidence, never permission to release quota. Birth
tokens are opaque and may only be compared for equality on the same machine.
Linux tokens include the boot ID so start ticks cannot collide across boots.
"""

import ctypes
from collections.abc import Mapping
import os
import sys
from pathlib import Path
from typing import Literal

_PLATFORM = sys.platform
_PROC_ROOT = Path("/proc")


def _valid_pid(pid: int) -> bool:
    return isinstance(pid, int) and not isinstance(pid, bool) and 0 < pid < 2**32


def _windows_api():
    """Declare pointer-safe signatures before opening a native handle."""
    from ctypes import wintypes

    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    api.OpenProcess.restype = wintypes.HANDLE
    api.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    api.WaitForSingleObject.restype = wintypes.DWORD
    api.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    api.GetProcessTimes.restype = wintypes.BOOL
    api.CloseHandle.argtypes = [wintypes.HANDLE]
    api.CloseHandle.restype = wintypes.BOOL
    return api


def _windows_query(pid: int, *, birth: bool) -> bool | str | None:
    handle = None
    api = None
    try:
        api = _windows_api()
        # SYNCHRONIZE permits a zero-time read-only wait; QUERY_LIMITED permits
        # creation-time queries. Neither right modifies or signals the process.
        handle = api.OpenProcess(0x00100000 | 0x1000, False, pid)
        if not handle:
            # With a validated PID and valid flags, ERROR_INVALID_PARAMETER
            # identifies a PID that is absent. Access denied remains unknown.
            return False if not birth and ctypes.get_last_error() == 87 else None
        if not birth:
            result = api.WaitForSingleObject(handle, 0)
            return {0: False, 258: True}.get(result)
        from ctypes import wintypes

        creation, exited, kernel, user = (wintypes.FILETIME() for _ in range(4))
        if not api.GetProcessTimes(handle, ctypes.byref(creation), ctypes.byref(exited),
                                   ctypes.byref(kernel), ctypes.byref(user)):
            return None
        ticks = (creation.dwHighDateTime << 32) | creation.dwLowDateTime
        return f"windows:{ticks}" if ticks > 0 else None
    except (OSError, AttributeError, TypeError, ValueError):
        return None
    finally:
        if handle and api is not None:
            try:
                api.CloseHandle(handle)
            except OSError:
                pass


def _linux_stat(pid: int) -> tuple[str, str] | None:
    text = (_PROC_ROOT / str(pid) / "stat").read_text(encoding="ascii")
    left, right = text.find("("), text.rfind(")")
    if left < 0 or right <= left or text[:left].strip() != str(pid):
        return None
    fields = text[right + 1:].split()
    # fields[0] is state (3); fields[19] is starttime (22). Names may
    # contain both spaces and ')' and cannot be parsed with plain split().
    if len(fields) < 20 or fields[0] not in {"R", "S", "D", "Z", "T", "t", "X", "x", "K", "W", "P", "I"}:
        return None
    if not fields[19].isascii() or not fields[19].isdigit() or int(fields[19]) <= 0:
        return None
    return fields[0], str(int(fields[19]))


def _linux_missing_pid(pid: int) -> bool | None:
    """Only infer absence when this proc mount exposes all process IDs."""
    try:
        if not _PROC_ROOT.is_dir() or (_PROC_ROOT / str(pid)).is_dir():
            return None
        mounts = (_PROC_ROOT / "mounts").read_text(encoding="ascii")
        visible_mount = False
        for line in mounts.splitlines():
            fields = line.split()
            if len(fields) < 4 or fields[2] != "proc":
                continue
            mountpoint = fields[1]
            for escaped, literal in (("\\040", " "), ("\\011", "\t"),
                                     ("\\012", "\n"), ("\\134", "\\")):
                mountpoint = mountpoint.replace(escaped, literal)
            if mountpoint != _PROC_ROOT.as_posix():
                continue
            if any(option.startswith("hidepid=") and option not in {"hidepid=0", "hidepid=off"}
                   for option in fields[3].split(",")):
                return None
            visible_mount = True
        if visible_mount:
            return False
    except (OSError, UnicodeError):
        pass
    return None


def process_alive(pid: int) -> bool | None:
    """Return liveness using read-only native/proc queries, or None if unknown."""
    if not _valid_pid(pid):
        return None
    if _PLATFORM == "win32":
        return _windows_query(pid, birth=False)
    if _PLATFORM.startswith("linux"):
        try:
            stat = _linux_stat(pid)
            return None if stat is None else stat[0] not in {"Z", "X", "x"}
        except FileNotFoundError:
            # hidepid mounts can hide existing processes as ENOENT.
            return _linux_missing_pid(pid)
        except (OSError, UnicodeError, ValueError):
            return None
    return None


def process_birth(pid: int) -> str | None:
    """Return an opaque creation token, retaining unknown on any read failure."""
    if not _valid_pid(pid):
        return None
    if _PLATFORM == "win32":
        return _windows_query(pid, birth=True)
    if _PLATFORM.startswith("linux"):
        try:
            stat = _linux_stat(pid)
            boot = (_PROC_ROOT / "sys/kernel/random/boot_id").read_text(encoding="ascii").strip()
            if stat is not None and boot and not any(char.isspace() for char in boot):
                return f"linux:{boot}:{stat[1]}"
        except (OSError, UnicodeError, ValueError):
            pass
    return None


def current_owner() -> dict:
    """Capture the current process identity for a new reservation."""
    pid = os.getpid()
    return {"pid": pid, "birth": process_birth(pid)}


def owner_status(owner: Mapping) -> Literal["alive", "dead", "unknown"]:
    """Distinguish an original owner from a later process reusing its PID."""
    if not isinstance(owner, Mapping) or not _valid_pid(owner.get("pid")):
        return "unknown"
    stored_birth = owner.get("birth")
    if stored_birth is not None and (not isinstance(stored_birth, str) or not stored_birth.strip()):
        return "unknown"
    pid = owner["pid"]
    alive = process_alive(pid)
    if alive is False:
        return "dead"
    birth = process_birth(pid)
    if stored_birth is not None and birth is not None:
        if birth != stored_birth:
            return "dead"
        if alive is True:
            return "alive"
    return "unknown"
