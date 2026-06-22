# 执行器与安全回归 原子写不毁文件 BOM保留 安全拦截按子命令 net解码 后台shell上限

from __future__ import annotations

from pathlib import Path

import pytest


# ---------- fs edit write 原子化 回写失败不截断原文件 BOM 保留 ----------

def test_edit_file_atomic_preserves_original_on_encode_failure(tmp_path):
    from desktop_pet.executor import fs
    p = tmp_path / "g.txt"
    original = "你好世界".encode("gbk")
    p.write_bytes(original)
    # 把内容改成含 emoji GBK 编不了 原子写该报失败 但绝不能把原文件截没
    out = fs.edit_file(str(p), "世界", "世界😀")
    assert out.startswith("[write failed"), f"GBK 编码失败该报错 得到: {out}"
    assert p.read_bytes() == original, "原文件必须分毫不动(原子写的意义)"


def test_edit_file_preserves_bom(tmp_path):
    from desktop_pet.executor import fs
    p = tmp_path / "b.txt"
    p.write_bytes(b"\xef\xbb\xbfhello world")  # UTF-8 BOM
    fs.edit_file(str(p), "world", "there")
    raw = p.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf"), "编辑后该保留 UTF-8 BOM"
    assert raw[3:] == b"hello there"


def test_write_file_no_spurious_bom(tmp_path):
    from desktop_pet.executor import fs
    p = tmp_path / "w.txt"
    fs.write_file(str(p), "纯utf8无bom")
    assert not p.read_bytes().startswith(b"\xef\xbb\xbf"), "新写文件不该凭空加 BOM"


# ---------- safety check_blocked 按子命令作用域 ----------

@pytest.mark.parametrize("cmd, should_block", [
    ("cd C:\\ ; rm -rf build", False),           # 裸根来自 cd 删的是 build 不该拦
    ("cd C:/ ; rm -rf node_modules", False),
    ("rm -rf .", False),                          # 删当前目录不是裸根
    ("rm -rf C:\\", True),                        # 同一子命令 裸根+删+递归 该拦
    ("rm -Recurse -Force C:\\Windows", True),
])
def test_check_blocked_per_subcommand(cmd, should_block):
    from desktop_pet.executor import safety
    blocked = safety.check_blocked(cmd) is not None
    assert blocked == should_block, f"{cmd!r} 拦截判断错(got blocked={blocked})"


# ---------- net 解码按 头charset body meta utf-8 gbk ----------

def test_net_decode_gbk_meta_no_mojibake():
    from desktop_pet.executor import net

    class _Resp:
        charset_encoding = None  # 头里没 charset

    raw = '<html><head><meta charset="gbk"></head><body>你好世界</body></html>'.encode("gbk")
    text = net._decode_body(_Resp(), raw)
    assert "你好世界" in text, "GBK <meta> 页面不该解成乱码"


def test_net_looks_binary():
    from desktop_pet.executor import net
    assert net._looks_binary(b"\x89PNG\r\n\x1a\n\x00\x00\x00")  # PNG 含 NUL
    assert not net._looks_binary("正常文本 normal text".encode("utf-8"))


# ---------- shell 后台任务并发上限 + shutdown_background 存在 ----------

def test_shell_has_shutdown_background():
    from desktop_pet.executor import shell
    assert hasattr(shell, "shutdown_background"), "退出清理后台 shell 的函数必须存在"
    assert shell._BG_MAX_RUNNING >= 1
