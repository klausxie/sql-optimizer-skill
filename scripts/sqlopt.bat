@echo off
rem sqlopt - SQL Optimizer CLI wrapper (Windows)
rem 复制到业务项目根目录使用
rem
rem 用法:
rem   sqlopt run init --config sqlopt.yml
rem   sqlopt mock <run_id>
rem
rem 环境变量:
rem   SQLOPT_HOME - sql-optimizer-skill 的安装路径，如 D:\tools\sql-optimizer-skill

if "%SQLOPT_HOME%"=="" (
    echo Error: SQLOPT_HOME environment variable is not set >&2
    echo Please set SQLOPT_HOME to your sql-optimizer-skill directory >&2
    echo Example: set SQLOPT_HOME=D:\tools\sql-optimizer-skill >&2
    exit /b 1
)

set PYTHONPATH=%SQLOPT_HOME%\python
python -m sqlopt.cli.main %*
