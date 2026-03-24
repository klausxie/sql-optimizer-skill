@echo off
rem sqlopt - SQL Optimizer CLI wrapper (Windows)
rem 复制到业务项目根目录使用
rem
rem 用法:
rem   sqlopt run init --config sqlopt.yml
rem   sqlopt mock <run_id>

set SCRIPT_DIR=%~dp0
set SQLOPT_DIR=%SQLOPT_DIR%
if "%SQLOPT_DIR%"=="" set SQLOPT_DIR=%SCRIPT_DIR%sql-optimizer-skill

set PYTHONPATH=%SQLOPT_DIR%\python
python -m sqlopt.cli.main %*
