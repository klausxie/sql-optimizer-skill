@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "SKILL_ROOT=%%~fI"

set "CONFIG_PATH=%~1"
if "%CONFIG_PATH%"=="" set "CONFIG_PATH=sqlopt.yml"

set "TO_STAGE=%~2"
if "%TO_STAGE%"=="" set "TO_STAGE=patch_generate"

set "RUN_ID=%~3"

set "MAX_STEPS=%~4"
if "%MAX_STEPS%"=="" set "MAX_STEPS=200"

set "MAX_SECONDS=%~5"
if "%MAX_SECONDS%"=="" set "MAX_SECONDS=95"

if exist "%SKILL_ROOT%\runtime\.venv\Scripts\python.exe" (
  set "PY=%SKILL_ROOT%\runtime\.venv\Scripts\python.exe"
  set "SCRIPT=%SKILL_ROOT%\runtime\scripts\run_until_budget.py"
) else (
  for %%I in ("%SKILL_ROOT%\..\..") do set "REPO_ROOT=%%~fI"
  set "PY=python"
  set "SCRIPT=%REPO_ROOT%\scripts\run_until_budget.py"
  if defined PYTHONPATH (
    set "PYTHONPATH=%REPO_ROOT%\python;%PYTHONPATH%"
  ) else (
    set "PYTHONPATH=%REPO_ROOT%\python"
  )
)

if not "%RUN_ID%"=="" (
  "%PY%" "%SCRIPT%" --config "%CONFIG_PATH%" --to-stage "%TO_STAGE%" --run-id "%RUN_ID%" --max-steps "%MAX_STEPS%" --max-seconds "%MAX_SECONDS%"
) else (
  "%PY%" "%SCRIPT%" --config "%CONFIG_PATH%" --to-stage "%TO_STAGE%" --max-steps "%MAX_STEPS%" --max-seconds "%MAX_SECONDS%"
)
