# 危险命令拦截：该拦的拦住，不该拦的放行（误杀比漏杀更影响日常使用）。
import pytest

from desktop_pet.executor.safety import check_blocked, check_risky


class TestBlocked:
    @pytest.mark.parametrize("cmd", [
        "rm -rf /",
        "rm -rf ~",
        "rm -rf ~/",
        "rm -rf /*",
        "Remove-Item -Recurse -Force C:\\",
        "del /s /q C:\\Windows",
        "rd /s /q c:\\users",
        "format c:",
        "diskpart",
        "cipher /w:C",
        "Clear-Disk -Number 0",
        'shutil.rmtree("C:\\")',
    ])
    def test_catastrophic_commands_blocked(self, cmd):
        assert check_blocked(cmd) is not None, cmd


class TestAllowed:
    @pytest.mark.parametrize("cmd", [
        "Remove-Item -Recurse -Force dist/",
        "rm -rf build/",
        "rm -rf ./node_modules",
        "rm -rf /tmp/foo",
        "del file.txt",
        "git rm -r --cached .",
        "Remove-Item -Recurse -Force .venv",
        "rm -f output.log",
        "echo hello / world",
        "ls ~/projects",
    ])
    def test_everyday_commands_pass(self, cmd):
        assert check_blocked(cmd) is None, cmd


class TestRisky:

    @pytest.mark.parametrize("cmd", [
        "git push --force origin main",
        "git push -f",
        "git push --force-with-lease origin dev",
        "git reset --hard HEAD~1",
        "git clean -fdx",
        "git checkout -- src/app.py",
        "shutdown /s /t 0",
        "Restart-Computer",
        "reg delete HKCU\\Software\\Foo",
        "Remove-Item -Recurse -Force node_modules",
        "rm -rf build/",
        'shutil.rmtree("dist")',
    ])
    def test_risky_commands_need_confirm(self, cmd):
        assert check_risky(cmd) is not None, cmd

    @pytest.mark.parametrize("cmd", [
        "git push origin main",
        "git status",
        "git checkout main",
        "git rm -r --cached .",
        "del file.txt",
        "ls ~/projects",
        "Get-Process",
        "echo may the force be with you",
    ])
    def test_everyday_commands_skip_confirm(self, cmd):
        assert check_risky(cmd) is None, cmd

    @pytest.mark.parametrize("cmd", [
        "rm -rf /",
        "format c:",
        "diskpart",
    ])
    def test_blocked_tier_returns_none(self, cmd):
        assert check_blocked(cmd) is not None, cmd
        assert check_risky(cmd) is None, cmd
