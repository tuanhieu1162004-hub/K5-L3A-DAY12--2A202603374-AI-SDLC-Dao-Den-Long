"""Current resident memory for the desktop verification commands."""

import ctypes
import os
import subprocess
import sys
from pathlib import Path


def rss_mb():
    if sys.platform == "win32":
        class Counters(ctypes.Structure):
            _fields_ = [("size", ctypes.c_ulong), ("faults", ctypes.c_ulong)] + [
                (name, ctypes.c_size_t)
                for name in ("peak", "working", "peak_paged", "paged", "peak_nonpaged",
                             "nonpaged", "pagefile", "peak_pagefile")
            ]

        counters = Counters()
        counters.size = ctypes.sizeof(counters)
        get_process = ctypes.windll.kernel32.GetCurrentProcess
        get_process.restype = ctypes.c_void_p
        measure = ctypes.windll.psapi.GetProcessMemoryInfo
        measure.argtypes = (ctypes.c_void_p, ctypes.POINTER(Counters), ctypes.c_ulong)
        if not measure(get_process(), ctypes.byref(counters), counters.size):
            raise OSError("GetProcessMemoryInfo failed")
        return counters.working / 1024**2
    if sys.platform.startswith("linux"):
        pages = int(Path("/proc/self/statm").read_text().split()[1])
        return pages * os.sysconf("SC_PAGE_SIZE") / 1024**2
    kib = subprocess.check_output(["ps", "-o", "rss=", "-p", str(os.getpid())], text=True)
    return int(kib.strip()) / 1024
