# author: bdth
# email: 2074055628@qq.com
# 系统内存查询与读取进程内存:统计内存占用 Top 进程,并按地址读取目标进程内存并十六进制转储

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
    """总内存占用 + 按 RSS 排序的 Top 进程。psutil 没装就直接返回提示，不当致命错。"""
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
            continue  # 进程在遍历途中退了 / 系统进程没权限 / 信息缺字段——跳过就好，别让一个坏进程毁掉整张表
    procs.sort(reverse=True)
    # top 可能是模型瞎传的字符串/负号/非数字，全兜到 _TOP_N；上限钉死 40，省得它要个几百行刷屏
    n = max(1, min(int(top) if str(top).lstrip("-").isdigit() else _TOP_N, 40))
    for rss, pid, name in procs[:n]:
        lines.append(f"  {_mb(rss):>10}  pid {pid:<7} {name}")
    return "\n".join(lines)


def read_process_memory(pid: int, address: int, size: int = 256) -> str:
    """按地址 dump 目标进程内存，十六进制转储。一切异常都吞成可读文案返回，不抛——调用方是 LLM 工具，崩了它不会处理。"""
    size = max(1, min(int(size), _MAX_READ))  # 上限 4096，别让单次读把上下文撑爆
    try:
        # base=0 让 int() 自己认前缀："0x..." 走十六进制、纯数字走十进制——模型两种都可能给
        addr = int(address, 0) if isinstance(address, str) else int(address)
    except (ValueError, TypeError):
        return f"[can't parse address: {address!r} (use decimal or 0x hex)]"

    # use_last_error=True 才能拿到 GetLastError；restype 不显式声明，64 位下句柄会被截成 int 变野指针
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
        # ok 为真也可能 read.value==0（跨页时部分成功/全失败），所以两个条件都得判
        if not ok or read.value == 0:
            err = ctypes.get_last_error()
            return f"[read failed @ {hex(addr)} (error {err}) — address may be unmapped/unreadable]"
        data = bytes(buf[: read.value])  # 只取实际读到的字节，缓冲区尾巴是脏的
        return f"Process {pid} @ {hex(addr)}, read {read.value} bytes:\n{_hexdump(data, addr)}"
    finally:
        k32.CloseHandle(handle)  # 句柄必须放 finally 关，中途 return 一堆，漏一个就泄露


def _hexdump(data: bytes, base: int) -> str:
    """xxd 风格转储。base 传真实起始地址，左列地址才对得上目标进程，不然只是偏移没意义。"""
    rows = []
    for i in range(0, len(data), 16):
        chunk = data[i : i + 16]
        hex_part = " ".join(f"{b:02x}" for b in chunk).ljust(47)  # 47 = 16*3-1，凑齐宽度好让右侧 ASCII 列对齐（末行不满 16 也对得上）
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)  # 非可打印字节统一画 "."，省得控制符把终端搞乱
        rows.append(f"{base + i:08x}  {hex_part}  {ascii_part}")
    return "\n".join(rows)
