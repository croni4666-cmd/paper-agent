"""Read-only process identity and conservative recovery ownership tests."""

import ctypes
import os
from pathlib import Path
import subprocess
import sys

import pytest
from pa_cli import process_identity as process_identity_module


@pytest.fixture
def identity(monkeypatch):
    def forbid_signal(*args, **kwargs):
        pytest.fail("identity queries must never signal processes")
    monkeypatch.setattr(os, "kill", forbid_signal)
    return process_identity_module


@pytest.mark.skipif(sys.platform != "win32" and not sys.platform.startswith("linux"), reason="native identity supports Windows/Linux")
def test_native_current_owner_identifies_this_process(identity):
    owner = identity.current_owner()
    assert owner["pid"] == os.getpid()
    assert isinstance(owner["birth"], str) and owner["birth"]
    assert identity.process_alive(owner["pid"]) is True
    assert identity.process_birth(owner["pid"]) == owner["birth"]
    assert identity.owner_status(owner) == "alive"


@pytest.mark.skipif(sys.platform != "win32" and not sys.platform.startswith("linux"), reason="native identity supports Windows/Linux")
def test_native_child_exit_is_dead_without_sending_a_signal(identity):
    child = subprocess.Popen(
        [sys.executable, "-c", "import sys; print('ready', flush=True); sys.stdin.readline()"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
    )
    try:
        assert child.stdout.readline().strip() == "ready"
        owner = {"pid": child.pid, "birth": identity.process_birth(child.pid)}
        assert owner["birth"]
        assert identity.owner_status(owner) == "alive"
    finally:
        child.communicate("done\n", timeout=10)
    assert identity.process_alive(child.pid) is False
    assert identity.owner_status(owner) == "dead"


@pytest.mark.parametrize("pid", [0, -1, True, "123", None, 2**32])
def test_invalid_pid_is_unknown(identity, pid):
    assert identity.process_alive(pid) is None
    assert identity.process_birth(pid) is None
    assert identity.owner_status({"pid": pid, "birth": "token"}) == "unknown"


@pytest.mark.parametrize(
    "alive,birth,stored,want",
    [(True, "new", "old", "dead"), (True, "same", "same", "alive"),
     (True, None, "old", "unknown"), (None, "same", "same", "unknown"),
     (None, "new", "old", "dead"), (False, None, "old", "dead"),
     (True, "new", None, "unknown"), (False, None, None, "dead")],
)
def test_owner_status_preserves_unknown_and_detects_pid_reuse(identity, monkeypatch, alive, birth, stored, want):
    monkeypatch.setattr(identity, "process_alive", lambda pid: alive)
    monkeypatch.setattr(identity, "process_birth", lambda pid: birth)
    assert identity.owner_status({"pid": 123, "birth": stored}) == want


@pytest.mark.parametrize("owner", [{}, {"pid": 123, "birth": 5}, {"pid": 123, "birth": ""}, None])
def test_malformed_owner_never_establishes_recoverable_death(identity, owner):
    assert identity.owner_status(owner) == "unknown"


def linux_proc(identity, monkeypatch, tmp_path, *, state="S", ticks="12345", boot="boot-a"):
    root = tmp_path / "proc"
    (root / "123").mkdir(parents=True)
    (root / "sys/kernel/random").mkdir(parents=True)
    # Fields 3..21 precede starttime (22). The name contains spaces and ')'.
    stat = "123 (a tricky ) process) " + " ".join([state] + ["0"] * 18 + [ticks] + ["0"] * 30)
    (root / "123/stat").write_text(stat, encoding="ascii")
    (root / "sys/kernel/random/boot_id").write_text(boot + "\n", encoding="ascii")
    mountpoint = root.as_posix().replace(" ", "\\040")
    (root / "mounts").write_text(f"proc {mountpoint} proc rw,relatime 0 0\n", encoding="ascii")
    monkeypatch.setattr(identity, "_PLATFORM", "linux")
    monkeypatch.setattr(identity, "_PROC_ROOT", root)
    return root


def test_linux_parses_parenthesized_name_and_binds_birth_to_boot(identity, monkeypatch, tmp_path):
    root = linux_proc(identity, monkeypatch, tmp_path)
    first = identity.process_birth(123)
    assert first == "linux:boot-a:12345"
    assert identity.process_alive(123) is True
    (root / "sys/kernel/random/boot_id").write_text("boot-b", encoding="ascii")
    assert identity.process_birth(123) == "linux:boot-b:12345"
    assert identity.owner_status({"pid": 123, "birth": first}) == "dead"


@pytest.mark.parametrize("state", ["Z", "X", "x"])
def test_linux_zombie_or_exited_process_is_dead(identity, monkeypatch, tmp_path, state):
    linux_proc(identity, monkeypatch, tmp_path, state=state)
    assert identity.process_alive(123) is False


@pytest.mark.parametrize("stat", ["", "123 bad", "123 (name) S 0", "123 (name) Q " + "0 " * 40])
def test_linux_malformed_stat_is_unknown(identity, monkeypatch, tmp_path, stat):
    root = linux_proc(identity, monkeypatch, tmp_path)
    (root / "123/stat").write_text(stat, encoding="ascii")
    assert identity.process_alive(123) is None
    assert identity.process_birth(123) is None


@pytest.mark.parametrize("ticks", ["bad", "-5", "0"])
def test_linux_invalid_start_ticks_is_unknown(identity, monkeypatch, tmp_path, ticks):
    linux_proc(identity, monkeypatch, tmp_path, ticks=ticks)
    assert identity.process_birth(123) is None


def test_linux_missing_proc_or_boot_does_not_fabricate_birth(identity, monkeypatch, tmp_path):
    root = linux_proc(identity, monkeypatch, tmp_path)
    assert identity.process_alive(456) is False
    assert identity.process_birth(456) is None
    (root / "sys/kernel/random/boot_id").unlink()
    assert identity.process_birth(123) is None
    assert identity.owner_status({"pid": 123, "birth": "old"}) == "unknown"


def test_linux_inaccessible_proc_is_unknown(identity, monkeypatch, tmp_path):
    linux_proc(identity, monkeypatch, tmp_path)
    def inaccessible(*args, **kwargs):
        raise PermissionError("unreadable proc")
    monkeypatch.setattr(Path, "read_text", inaccessible)
    assert identity.process_alive(123) is None
    assert identity.process_birth(123) is None


@pytest.mark.parametrize("restriction", ["hidepid=1", "hidepid=2", "hidepid=invisible"])
def test_linux_hidden_pid_is_unknown_not_dead(identity, monkeypatch, tmp_path, restriction):
    root = linux_proc(identity, monkeypatch, tmp_path)
    mounts = (root / "mounts").read_text(encoding="ascii").replace("rw,relatime", f"rw,relatime,{restriction}")
    (root / "mounts").write_text(mounts, encoding="ascii")
    assert identity.process_alive(456) is None
    assert identity.owner_status({"pid": 456, "birth": "old"}) == "unknown"


def test_linux_missing_mount_visibility_metadata_is_unknown(identity, monkeypatch, tmp_path):
    root = linux_proc(identity, monkeypatch, tmp_path)
    (root / "mounts").unlink()
    assert identity.process_alive(456) is None


def test_linux_restricted_mount_cannot_be_masked_by_another_mount_entry(identity, monkeypatch, tmp_path):
    root = linux_proc(identity, monkeypatch, tmp_path)
    mounts = (root / "mounts").read_text(encoding="ascii")
    (root / "mounts").write_text(mounts + mounts.replace("rw,relatime", "rw,hidepid=2"), encoding="ascii")
    assert identity.process_alive(456) is None


def test_linux_missing_proc_filesystem_is_unknown(identity, monkeypatch, tmp_path):
    monkeypatch.setattr(identity, "_PLATFORM", "linux")
    monkeypatch.setattr(identity, "_PROC_ROOT", tmp_path / "not-mounted")
    assert identity.process_alive(123) is None
    assert identity.process_birth(123) is None


def test_unsupported_platform_is_unknown(identity, monkeypatch):
    monkeypatch.setattr(identity, "_PLATFORM", "unsupported")
    assert identity.process_alive(os.getpid()) is None
    assert identity.process_birth(os.getpid()) is None
    assert identity.current_owner() == {"pid": os.getpid(), "birth": None}


class NativeFunction:
    def __init__(self, callback):
        self.callback = callback
    def __call__(self, *args):
        return self.callback(*args)


def windows_api(identity, monkeypatch, *, handle=123, wait=258, times_ok=True, error=5, raise_times=False):
    from ctypes import wintypes
    closed = []
    def open_process(access, inherit, pid):
        assert access == 0x00100000 | 0x1000
        assert not inherit and pid == 123
        return handle
    def get_times(process, creation, exit_time, kernel, user):
        if raise_times:
            raise OSError("native failure")
        value = ctypes.cast(creation, ctypes.POINTER(wintypes.FILETIME)).contents
        value.dwHighDateTime, value.dwLowDateTime = 2, 3
        return times_ok
    class DLL:
        OpenProcess = NativeFunction(open_process)
        WaitForSingleObject = NativeFunction(lambda process, timeout: wait)
        GetProcessTimes = NativeFunction(get_times)
        CloseHandle = NativeFunction(lambda process: closed.append(process) or True)
    api = DLL()
    monkeypatch.setattr(identity, "_PLATFORM", "win32")
    monkeypatch.setattr(ctypes, "WinDLL", lambda *a, **k: api, raising=False)
    monkeypatch.setattr(ctypes, "get_last_error", lambda: error, raising=False)
    return closed, api


def test_windows_uses_typed_handles_and_closes_queries(identity, monkeypatch):
    closed, api = windows_api(identity, monkeypatch)
    assert identity.process_alive(123) is True
    assert identity.process_birth(123) == "windows:8589934595"
    assert closed == [123, 123]
    from ctypes import wintypes
    assert api.OpenProcess.restype is wintypes.HANDLE
    assert api.OpenProcess.argtypes == [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    assert api.GetProcessTimes.argtypes[0] is wintypes.HANDLE
    assert api.WaitForSingleObject.argtypes == [wintypes.HANDLE, wintypes.DWORD]
    assert api.CloseHandle.argtypes == [wintypes.HANDLE]


@pytest.mark.parametrize("error,want", [(87, False), (5, None), (0, None)])
def test_windows_failed_open_is_unknown_unless_pid_definitely_absent(identity, monkeypatch, error, want):
    closed, _ = windows_api(identity, monkeypatch, handle=None, error=error)
    assert identity.process_alive(123) is want
    assert identity.process_birth(123) is None
    assert closed == []


@pytest.mark.parametrize("wait,want", [(0, False), (258, True), (0xFFFFFFFF, None), (42, None)])
def test_windows_wait_result_distinguishes_exit_and_failure(identity, monkeypatch, wait, want):
    closed, _ = windows_api(identity, monkeypatch, wait=wait)
    assert identity.process_alive(123) is want
    assert closed == [123]


@pytest.mark.parametrize("raise_times", [False, True])
def test_windows_failed_birth_stays_unknown_and_closes_handle(identity, monkeypatch, raise_times):
    closed, _ = windows_api(identity, monkeypatch, times_ok=False, raise_times=raise_times)
    assert identity.process_birth(123) is None
    assert closed == [123]


def test_windows_unavailable_native_library_is_unknown(identity, monkeypatch):
    monkeypatch.setattr(identity, "_PLATFORM", "win32")
    def unavailable(*args, **kwargs):
        raise OSError("native API unavailable")
    monkeypatch.setattr(ctypes, "WinDLL", unavailable, raising=False)
    assert identity.process_alive(123) is None
    assert identity.process_birth(123) is None
