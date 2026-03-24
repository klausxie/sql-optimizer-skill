@echo off
rem sqlopt - SQL Optimizer CLI wrapper (Windows)
rem
rem Edit the paths below before running:
rem   SQLOPT_HOME - path to sql-optimizer-skill
rem   WORKDIR     - path to your business project (where sqlopt.yml is)

setlocal enabledelayedexpansion

rem ==== CONFIG ====
set "SQLOPT_HOME=D:\path\to\sql-optimizer-skill"
set "WORKDIR=D:\path\to\your\mybatis-project"
rem ==== CONFIG ====

if not exist "%SQLOPT_HOME%" (
    echo Error: SQLOPT_HOME directory not found: %SQLOPT_HOME%
    echo Please edit this script and set the correct path
    exit /b 1
)

if not exist "%WORKDIR%" (
    echo Error: WORKDIR directory not found: %WORKDIR%
    echo Please edit this script and set the correct path
    exit /b 1
)

cd /d "%WORKDIR%"
set "PYTHONPATH=%SQLOPT_HOME%\python"
python -m sqlopt.cli.main %*
