#!/usr/bin/env python3
"""
SQL Optimizer Build Script

Builds a standalone executable using PyInstaller.

Usage:
    python build.py              # Build for current platform
    python build.py --clean     # Clean build artifacts first
    python build.py --onefile   # Build single executable file
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def get_project_root() -> Path:
    return Path(__file__).resolve().parent


def check_dependencies():
    """Check if PyInstaller is installed."""
    try:
        import PyInstaller

        print(f"PyInstaller version: {PyInstaller.__version__}")
        return True
    except ImportError:
        print("PyInstaller not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        return True


def clean_build():
    """Remove build artifacts."""
    root = get_project_root()
    dirs_to_remove = ["build", "dist", "__pycache__"]

    for d in dirs_to_remove:
        path = root / d
        if path.exists():
            print(f"Removing {path}...")
            shutil.rmtree(path)

    # Also remove spec cache
    for spec_file in root.glob("*.spec"):
        if spec_file.name != "sqlopt.spec":
            spec_file.unlink()


def build(onefile: bool = False):
    """Build the executable."""
    root = get_project_root()

    # Check dependencies
    check_dependencies()

    # Build command
    cmd = [sys.executable, "-m", "PyInstaller"]

    if onefile:
        cmd.append("--onefile")
        cmd.append("--name=sqlopt")
    else:
        cmd.append("--onedir")
        cmd.append("--name=sqlopt")

    cmd.append("sqlopt.spec")

    print(f"Running: {' '.join(cmd)}")
    subprocess.check_call(cmd, cwd=str(root))

    # Find built executable
    if onefile:
        exe_path = root / "dist" / "sqlopt"
        if sys.platform == "win32":
            exe_path = root / "dist" / "sqlopt.exe"
    else:
        exe_path = root / "dist" / "sqlopt"
        if sys.platform == "win32":
            exe_path = root / "dist" / "sqlopt" / "sqlopt.exe"

    if exe_path.exists():
        print(f"\n✅ Build successful!")
        print(f"Executable: {exe_path}")

        if onefile:
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f"Size: {size_mb:.2f} MB")
    else:
        print(f"\n❌ Build may have failed. Check {root / 'dist'}")


def main():
    parser = argparse.ArgumentParser(description="SQL Optimizer Build Script")
    parser.add_argument(
        "--clean", action="store_true", help="Clean build artifacts before building"
    )
    parser.add_argument(
        "--onefile", action="store_true", help="Build as single executable file"
    )

    args = parser.parse_args()

    if args.clean:
        clean_build()

    build(onefile=args.onefile)


if __name__ == "__main__":
    main()
