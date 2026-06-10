# 让 tests 能直接 import desktop_pet（项目未打包安装，uv package=false）
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
