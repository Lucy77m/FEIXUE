# author: bdth
# email: 2074055628@qq.com
# 系统内存查询与读取进程内存:统计内存占用 Top 进程,并通过 Windows API 按地址读取目标进程内存并十六进制转储

from __future__ import annotations

import ctypes
from ctypes import wintypes

_TOP_N = 12
_MAX_READ = 4096
_PROCESS_VM_READ = 0x0010
_PROCESS_QUERY_INFORMATION = 0x0400


def _mb(n: int) -> str:
    return f"{n / 1024 / 1024:,.0f} MB"


def system_memory(top: int = _TOP_N) -> str:
    try:
        import psutil
    except ImportError:
        return "[memory stats unavailable: psutil not installed]"
    vm = psutil.virtual_memory()
    lines = [
        f"Memory: {_mb(vm.total)} total, {_mb(vm.used)} used ({vm.percent:.0f}%), {_mb(vm.available)} available",
        "",
        "Top processes by usage:",
    ]
    procs = []
    for p in psutil.process_iter(["pid", "name", "memory_info"]):
        try:
            rss = p.info["memory_info"].rss if p.info["memory_info"] else 0
            procs.append((rss, p.info["pid"], p.info["name"] or "?"))
        except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
            continue
    procs.sort(reverse=True)
    n = max(1, min(int(top) if str(top).lstrip("-").isdigit() else _TOP_N, 40))
    for rss, pid, name in procs[:n]:
        lines.append(f"  {_mb(rss):>10}  pid {pid:<7} {name}")
    return "\n".join(lines)


def read_process_memory(pid: int, address: int, size: int = 256) -> str:
    size = max(1, min(int(size), _MAX_READ))
    try:
        addr = int(address, 0) if isinstance(address, str) else int(address)
    except (ValueError, TypeError):
        return f"[can't parse address: {address!r} (use decimal or 0x hex)]"

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.OpenProcess.restype = wintypes.HANDLE
    k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    handle = k32.OpenProcess(_PROCESS_VM_READ | _PROCESS_QUERY_INFORMATION, False, int(pid))
    if not handle:
        err = ctypes.get_last_error() or "access denied"
        return f"[can't open process {pid} ({err}) — may need admin, or the process is protected/gone]"
    try:
        buf = (ctypes.c_ubyte * size)()
        read = ctypes.c_size_t(0)
        k32.ReadProcessMemory.argtypes = [
            wintypes.HANDLE, wintypes.LPCVOID, wintypes.LPVOID, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)
        ]
        ok = k32.ReadProcessMemory(handle, ctypes.c_void_p(addr), buf, size, ctypes.byref(read))
        if not ok or read.value == 0:
            err = ctypes.get_last_error()
            return f"[read failed @ {hex(addr)} (error {err}) — address may be unmapped/unreadable]"
        data = bytes(buf[: read.value])
        return f"Process {pid} @ {hex(addr)}, read {read.value} bytes:\n{_hexdump(data, addr)}"
    finally:
        k32.CloseHandle(handle)


def _hexdump(data: bytes, base: int) -> str:
    rows = []
    for i in range(0, len(data), 16):
        chunk = data[i : i + 16]
        hex_part = " ".join(f"{b:02x}" for b in chunk).ljust(47)
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        rows.append(f"{base + i:08x}  {hex_part}  {ascii_part}")
    return "\n".join(rows)
