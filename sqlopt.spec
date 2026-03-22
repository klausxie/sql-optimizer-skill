# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for SQL Optimizer CLI

Usage:
    pyinstaller sqlopt.spec
    or
    python build.py
"""

import sys
from pathlib import Path

block_cipher = None

# Project root
ROOT = Path(__file__).resolve().parent
PYTHON_DIR = ROOT / "python"

a = Analysis(
    [PYTHON_DIR / "sqlopt" / "cli" / "main.py"],
    pathex=[str(PYTHON_DIR)],
    binaries=[],
    datas=[],
    hiddenimports=[
        # Database drivers
        "psycopg2",
        "psycopg2.extensions",
        "psycopg2.extras",
        "pymysql",
        "pymysql.connections",
        "pymysql.cursors",
        # Core dependencies
        "jsonschema",
        "yaml",
        "jsonpath_ng",
        "rich",
        "rich.console",
        "rich.table",
        "rich.progress",
        # CLI modules
        "sqlopt.cli.main",
        "sqlopt.cli.data_cli",
        "sqlopt.cli.contracts_cli",
        # Application modules
        "sqlopt.application",
        "sqlopt.application.workflow_v9",
        "sqlopt.application.v9_stages",
        "sqlopt.application.v9_stages.init",
        "sqlopt.application.v9_stages.parse",
        "sqlopt.application.v9_stages.recognition",
        "sqlopt.application.v9_stages.optimize",
        "sqlopt.application.v9_stages.patch",
        "sqlopt.application.v9_stages.runtime",
        "sqlopt.application.v9_stages.common",
        # Platform modules
        "sqlopt.platforms.sql.db_connectivity",
        "sqlopt.platforms.sql.schema_metadata",
        # Config
        "sqlopt.config",
        "sqlopt.configuration",
        # Run paths
        "sqlopt.run_paths",
    ],
    hookspath=[],
    hooksconfig={},
    keys=[],
    debug=False,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="sqlopt",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    **{
        "python_is_python3": True,
    }
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="sqlopt",
)
