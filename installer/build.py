#!/usr/bin/env python3
"""
SQL Optimizer 构建脚本

使用方法:
    python build.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> None:
    print("=" * 50)
    print("SQL Optimizer 构建脚本")
    print("=" * 50)
    print()

    py_version = sys.version_info
    print(f"Python 版本: {py_version.major}.{py_version.minor}.{py_version.micro}")
    if py_version < (3, 9):
        print("错误: 需要 Python >= 3.9")
        sys.exit(1)
    print()

    print("检查依赖...")
    try:
        import PyInstaller  # type: ignore
    except ImportError:
        print("错误: PyInstaller 未安装")
        print("请运行: pip install pyinstaller")
        sys.exit(1)
    print("PyInstaller 已安装")
    print()

    root = Path(__file__).parent.resolve()
    dist = root / "dist"
    config_src = root / "config"
    config_dest = dist / "config"

    dist.mkdir(exist_ok=True)
    (dist / "config" / "templates").mkdir(parents=True, exist_ok=True)
    print("创建输出目录...")
    print()

    print("清理旧构建...")
    build_dir = root / "build"
    old_exe = dist / ("sqlopt.exe" if sys.platform == "win32" else "sqlopt")

    for path in [build_dir, old_exe]:
        if path.exists():
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
            print(f"  已删除: {path.name}")
    print()

    print("开始构建...")
    src_file = root / ".." / "python" / "sqlopt" / "cli" / "main.py"

    if not src_file.exists():
        print(f"错误: 源码文件不存在: {src_file}")
        sys.exit(1)

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--name",
        "sqlopt",
        "--add-data",
        f"{config_src}{os.pathsep}templates",
        "--console",
        str(src_file),
    ]

    print(f"执行: {' '.join(cmd)}")
    print()

    try:
        subprocess.run(cmd, check=True, cwd=str(root.parent))
    except subprocess.CalledProcessError as e:
        print(f"错误: PyInstaller 构建失败 (退出码: {e.returncode})")
        sys.exit(1)

    print()
    print("复制配置文件...")
    if config_src.exists():
        if config_dest.exists():
            shutil.rmtree(config_dest)
        shutil.copytree(config_src, config_dest)
        print(f"  已复制: {config_dest}")
    print()

    print("=" * 50)
    print("构建完成!")
    print("=" * 50)
    print()
    exe_name = "sqlopt.exe" if sys.platform == "win32" else "sqlopt"
    print(f"输出目录: {dist}")
    print(f"可执行文件: {dist / exe_name}")
    print()
    print("分发时，请将 dist/ 目录完整提供即可")


if __name__ == "__main__":
    main()
