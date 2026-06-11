# author: bdth
# email: 2074055628@qq.com
# 安全护栏回归测试 钉死 check_blocked / check_risky 的边界
# 这层是去掉沙箱后唯一的兜底 改正则前后都跑一遍 红了就是写漏了

import pytest

from desktop_pet.executor.safety import check_blocked, check_risky


# ── check_blocked：必须硬拦的灾难级操作（命中返回原因，None = 漏网 = 失败）──
MUST_BLOCK = [
    "format c:",
    "FORMAT D:",
    "diskpart",
    "Clear-Disk -Number 0",
    "Remove-Partition -DiskNumber 0 -PartitionNumber 2",
    "Initialize-Disk -Number 1",
    "cipher /w:C",
    r"reg delete HKLM\Software\Foo /f",
    "reg delete HKEY_LOCAL_MACHINE\\SYSTEM /f",
    'shutil.rmtree("/")',
    'shutil.rmtree("C:")',
    "os.removedirs('/')",
    r"Remove-Item C:\ -Recurse -Force",
    "rm -rf /",
    "del /s /q C:\\*",
    r"rd /s /q C:\Windows\System32",
]


# ── check_blocked：必须放行的日常命令（误杀比漏网更高频，这组守假阳性）──
MUST_PASS = [
    "git rm --cached secret.env",            # 删除动词但无递归无裸根
    "format-list",                           # 不是 format <盘>:
    r"Remove-Item .\node_modules -Recurse -Force",  # 子目录，非裸根（走 risky 确认，不该硬拦）
    r"rd /s build\temp",                     # 有子路径，非裸根
    r"ls C:\Users\me\proj",                  # 没有删除动词
    "diskpartition_helper.py",               # 不是 \bdiskpart\b
    "git diff --stat",
    "python -m pytest -q",
]


@pytest.mark.parametrize("cmd", MUST_BLOCK)
def test_blocks_catastrophic(cmd):
    assert check_blocked(cmd) is not None, f"该硬拦却放过了: {cmd!r}"


@pytest.mark.parametrize("cmd", MUST_PASS)
def test_blocked_allows_normal(cmd):
    assert check_blocked(cmd) is None, f"误杀了正常命令: {cmd!r}"


# ── check_risky：必须弹确认的高危但可恢复操作（命中返回中文原因）──
MUST_RISK = [
    "git push --force origin main",
    "git push -f",
    "git push --force-with-lease",
    "git reset --hard HEAD~1",
    "git clean -fd",
    "git checkout -- src/app.py",
    "shutdown /s /t 0",
    "Restart-Computer",
    "Stop-Computer",
    "Format-Volume -DriveLetter D",
    r"reg delete HKCU\Software\X",           # 非 HKLM/无 /f，硬拦不到，降级为确认
    "Remove-ItemProperty -Path HKCU:\\X -Name Y",
    'shutil.rmtree("./build")',
    r"Remove-Item .\dist -Recurse -Force",   # 删除动词 + 递归
]


# ── check_risky：必须放行的命令（None）──
MUST_NOT_RISK = [
    "git rm --cached secret.env",            # 白名单，且无递归
    "git status",
    "git push origin main",                  # 无 force
    "Remove-Item single_file.txt",           # 无递归无强制
    "ls -la",
    "git commit -m fix",
]


@pytest.mark.parametrize("cmd", MUST_RISK)
def test_risky_warns(cmd):
    assert check_risky(cmd) is not None, f"该弹确认却放过了: {cmd!r}"


@pytest.mark.parametrize("cmd", MUST_NOT_RISK)
def test_risky_allows_normal(cmd):
    assert check_risky(cmd) is None, f"误判为高危: {cmd!r}"


# ── 优先级：已被硬拦的命令不重复 warn（check_risky 返回 None，由 block 接管）──
@pytest.mark.parametrize("cmd", ["format c:", "rm -rf /", "diskpart"])
def test_blocked_takes_precedence_over_risky(cmd):
    assert check_blocked(cmd) is not None
    assert check_risky(cmd) is None, f"已硬拦还重复 warn: {cmd!r}"
