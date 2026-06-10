# read_file 的 offset 续读、search/glob 的目录剪枝与 GBK 回退。
from desktop_pet.executor import fs


class TestReadOffset:
    def test_small_file_returned_verbatim(self, tmp_path):
        p = tmp_path / "a.txt"
        p.write_text("hello", encoding="utf-8")
        assert fs.read_file(str(p)) == "hello"

    def test_truncation_note_gives_continue_offset(self, tmp_path):
        p = tmp_path / "big.txt"
        p.write_text("x" * 25000, encoding="utf-8")
        out = fs.read_file(str(p))
        assert "offset=20000" in out
        out2 = fs.read_file(str(p), offset=20000)
        assert "[end of file]" in out2
        assert "chars 20000–25000 of 25000" in out2

    def test_offset_past_end(self, tmp_path):
        p = tmp_path / "a.txt"
        p.write_text("hi", encoding="utf-8")
        assert "past the end" in fs.read_file(str(p), offset=10)


class TestPruningAndEncoding:
    def test_glob_skips_ignored_dirs(self, tmp_path):
        (tmp_path / "node_modules" / "pkg").mkdir(parents=True)
        (tmp_path / "node_modules" / "pkg" / "x.py").write_text("a", encoding="utf-8")
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "y.py").write_text("b", encoding="utf-8")
        out = fs.glob_files("*.py", str(tmp_path))
        assert "y.py" in out
        assert "node_modules" not in out

    def test_glob_matches_relative_path_pattern(self, tmp_path):
        (tmp_path / "pkg").mkdir()
        (tmp_path / "pkg" / "test_a.py").write_text("a", encoding="utf-8")
        out = fs.glob_files("**/test_*.py", str(tmp_path))
        assert "test_a.py" in out

    def test_search_skips_ignored_dirs(self, tmp_path):
        (tmp_path / ".venv").mkdir()
        (tmp_path / ".venv" / "z.py").write_text("NEEDLE", encoding="utf-8")
        (tmp_path / "ok.py").write_text("NEEDLE", encoding="utf-8")
        out = fs.search_code("NEEDLE", str(tmp_path))
        assert "ok.py" in out
        assert ".venv" not in out

    def test_search_finds_gbk_chinese(self, tmp_path):
        p = tmp_path / "g.py"
        p.write_bytes("# 中文注释\n".encode("gbk"))
        out = fs.search_code("中文", str(tmp_path))
        assert "g.py" in out
