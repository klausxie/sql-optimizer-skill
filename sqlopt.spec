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
import os

block_cipher = None

# Project root - relative to this spec file (works on both Mac and Windows)
ROOT = Path(SPECPATH)  # SPECPATH is PyInstaller's built-in variable pointing to spec file directory
PYTHON_DIR = ROOT / "python"

a = Analysis(
    [str(PYTHON_DIR / "sqlopt" / "cli" / "main.py")],
    pathex=[str(PYTHON_DIR)],
    binaries=[],
    datas=[
        # Include contracts directory for JSON schemas
        (str(ROOT / "contracts"), "contracts"),
        # Include templates directory for example configs
        (str(ROOT / "templates"), "templates"),
    ],
    hiddenimports=[
        # Database drivers (ONLY these)
        "psycopg2",
        "psycopg2.extensions",
        "psycopg2.extras",
        "pymysql",
        "pymysql.connections",
        # Core dependencies (ONLY these)
        "jsonschema",
        "yaml",
        "jsonpath_ng",
        "rich",
        "rich.console",
        "rich.table",
        "rich.progress",
        "rich.panel",
        "rich.measure",
        "rich.table",
        # CLI modules
        "sqlopt.cli.main",
        "sqlopt.cli.data_cli",
        "sqlopt.cli.contracts_cli",
        # Application modules (minimal)
        "sqlopt.application.workflow_v9",
        "sqlopt.application.v9_stages",
        "sqlopt.application.v9_stages.init",
        "sqlopt.application.v9_stages.parse",
        "sqlopt.application.v9_stages.recognition",
        "sqlopt.application.v9_stages.optimize",
        "sqlopt.application.v9_stages.patch",
        "sqlopt.application.v9_stages.runtime",
        "sqlopt.application.v9_stages.common",
        "sqlopt.application.v9_stages.param_example",
        # Platform modules
        "sqlopt.platforms.sql.db_connectivity",
        "sqlopt.platforms.sql.schema_metadata",
        "sqlopt.platforms.sql.optimizer_sql",
        "sqlopt.platforms.sql.metadata_evidence",
        # Config
        "sqlopt.config",
        "sqlopt.configuration",
        "sqlopt.configuration.defaults",
        "sqlopt.configuration.validation",
        "sqlopt.configuration.versioning",
        "sqlopt.configuration.common",
        "sqlopt.configuration.diagnostics",
        # Run paths
        "sqlopt.run_paths",
        # Shared
        "sqlopt.shared.xml_utils",
        "sqlopt.shared",
        # Stages
        "sqlopt.stages",
        # Other
        "sqlopt.progress",
        "sqlopt.manifest",
        "sqlopt.utils",
        "sqlopt.errors",
        "sqlopt.reason_codes",
        "sqlopt.failure_classification",
        "sqlopt.constants",
        "sqlopt.install_support",
    ],
    hookspath=[],
    hooksconfig={},
    keys=[],
    debug=False,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
    exclude_binaries=[
        # Exclude unnecessary packages
        "babel",
        "matplotlib",
        "sphinx",
        "numpy",
        "pandas",
        "PIL",
        "tkinter",
        "_tkinter",
        "jedi",
        "ipython",
        "notebook",
        "jupyter",
        "sphinx",
        "docutils",
        "zope",
        "pkg_resources",
        "setuptools",
    ],
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
