# fs 执行器的编码处理：read_file 与 edit_file 必须用同一套解码（utf-8 → gbk 回退）。
from desktop_pet.executor import fs


class TestReadFile:
    def test_reads_gbk_file(self, tmp_path):
        p = tmp_path / "g.txt"
        p.write_bytes("中文内容，GBK 编码".encode("gbk"))
        assert "中文内容" in fs.read_file(str(p))

    def test_reads_utf8_bom(self, tmp_path):
        p = tmp_path / "b.txt"
        p.write_bytes("﻿hello 世界".encode("utf-8"))
        out = fs.read_file(str(p))
        assert "hello 世界" in out and "﻿" not in out

    def test_missing_file(self, tmp_path):
        assert "doesn't exist" in fs.read_file(str(tmp_path / "nope.txt"))


class TestEditFile:
    def test_edit_gbk_file_preserves_encoding(self, tmp_path):
        p = tmp_path / "g.py"
        p.write_bytes("name = '旧值'\n".encode("gbk"))
        out = fs.edit_file(str(p), "旧值", "新值")
        assert "Replaced" in out
        assert p.read_bytes().decode("gbk") == "name = '新值'\n"

    def test_edit_preserves_crlf(self, tmp_path):
        p = tmp_path / "c.txt"
        p.write_bytes(b"line one\r\nline two\r\n")
        out = fs.edit_file(str(p), "line two", "line 2")
        assert "Replaced" in out
        assert p.read_bytes() == b"line one\r\nline 2\r\n"

    def test_ambiguous_without_replace_all(self, tmp_path):
        p = tmp_path / "a.txt"
        p.write_text("x = 1\nx = 1\n", encoding="utf-8")
        assert "ambiguous" in fs.edit_file(str(p), "x = 1", "x = 2")
