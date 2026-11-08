"""Processes this test run owns (its myLibrary test servers): on Windows they go into a job
object that Windows closes when the pytest process ends, however it ends (finished, killed,
timed out), and closing it ends every process in it. So a stopped or killed test run leaves no
test server behind.

- Only processes started through start() are in it: never the user's own myLibrary, VS Code
  or any other process.
- The job's handle can't be inherited (no security attributes), so child processes don't
  keep it open.
- A server is created suspended, put into the job, then resumed: the venv's python.exe
  launcher starts the real interpreter as a child, and that child is in the job from its start.
- If containment can't be set up, start() raises: it's never silently skipped.
- Elsewhere than Windows, processes start normally (the CI and development machines are
  Windows)."""

from __future__ import annotations

import subprocess
import sys

_job = None


if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _ntdll = ctypes.WinDLL("ntdll")
    _kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    _kernel32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
    _kernel32.SetInformationJobObject.argtypes = [
        wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]  # fmt: skip
    _kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    _ntdll.NtResumeProcess.argtypes = [wintypes.HANDLE]

    class _BasicLimits(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class _IoCounters(ctypes.Structure):
        _fields_ = [(name, ctypes.c_uint64) for name in (
            "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
            "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]  # fmt: skip

    class _ExtendedLimits(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", _BasicLimits),
            ("IoInfo", _IoCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    _KILL_ON_JOB_CLOSE = 0x2000
    _EXTENDED_LIMITS = 9  # JobObjectExtendedLimitInformation
    _CREATE_SUSPENDED = 0x00000004

    def _the_job():
        global _job
        if _job is None:
            job = _kernel32.CreateJobObjectW(None, None)  # no attributes: not inheritable
            if not job:
                raise OSError(ctypes.get_last_error(), "CreateJobObject failed")
            limits = _ExtendedLimits()
            limits.BasicLimitInformation.LimitFlags = _KILL_ON_JOB_CLOSE
            if not _kernel32.SetInformationJobObject(
                job, _EXTENDED_LIMITS, ctypes.byref(limits), ctypes.sizeof(limits)
            ):
                raise OSError(ctypes.get_last_error(), "SetInformationJobObject failed")
            _job = job
        return _job

    def start(command: list[str], **popen) -> subprocess.Popen:
        """subprocess.Popen(command, **popen), owned by this test run (see above)."""
        job = _the_job()
        popen["creationflags"] = popen.get("creationflags", 0) | _CREATE_SUSPENDED
        process = subprocess.Popen(command, **popen)
        handle = wintypes.HANDLE(int(process._handle))
        try:
            if not _kernel32.AssignProcessToJobObject(job, handle):
                raise OSError(ctypes.get_last_error(), "AssignProcessToJobObject failed")
        except BaseException:
            process.kill()
            process.wait(10)
            raise
        finally:
            _ntdll.NtResumeProcess(handle)
        return process

else:

    def start(command: list[str], **popen) -> subprocess.Popen:
        return subprocess.Popen(command, **popen)
