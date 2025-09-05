@echo off
setlocal enabledelayedexpansion

REM Simple task runner for Windows CMD (no external deps)
REM Usage: tasks <init|install|pre-commit|lint|format|type|test|run|css|help>

set TASK=%1
if "%TASK%"=="" goto :help

if /I "%TASK%"=="init"  goto :init
if /I "%TASK%"=="install"  goto :install
if /I "%TASK%"=="pre-commit" goto :precommit
if /I "%TASK%"=="lint"  goto :lint
if /I "%TASK%"=="format"  goto :format
if /I "%TASK%"=="type"  goto :type
if /I "%TASK%"=="test"  goto :test
if /I "%TASK%"=="run"  goto :run
if /I "%TASK%"=="css"  goto :css
if /I "%TASK%"=="report"  goto :report
if /I "%TASK%"=="help"  goto :help

echo Unknown task: %TASK%
exit /b 1

:init
call :install || exit /b 1
pre-commit install
exit /b %ERRORLEVEL%

:install
python -m pip install --upgrade pip || exit /b 1
pip install -e ".[dev]"
exit /b %ERRORLEVEL%

:precommit
pre-commit install
exit /b %ERRORLEVEL%

:lint
ruff check . || exit /b 1
black --check . || exit /b 1
isort --check-only . || exit /b 1
exit /b 0

:format
black . || exit /b 1
isort . || exit /b 1
ruff check --fix . || exit /b 1
exit /b 0

:type
mypy app
exit /b %ERRORLEVEL%

:test
pytest --cov=app --cov-report=term-missing --cov-fail-under=80
exit /b %ERRORLEVEL%

:run
uvicorn app.main:app --reload
exit /b %ERRORLEVEL%

:css
where sass >nul 2>nul
if %ERRORLEVEL%==0 (
  sass app\static\scss\main.scss app\static\css\app.css --no-source-map --style=compressed
  ) else (
  echo [INFO] 'sass' no encontrado. Omite compilacion SCSS.
  echo  Instala Dart Sass (ej.: npm install -g sass) si quieres compilar SCSS.
)
exit /b 0

:report
if not exist reports mkdir reports
pytest --cov=app --cov-report=term-missing --cov-report=html ^
  --html=reports\tests.html --self-contained-html ^
  --junitxml=reports\junit.xml
exit /b %ERRORLEVEL%

:help
echo Uso: tasks ^<tarea^>
echo  Tareas: init, install, pre-commit, lint, format, type, test, run, css, help
exit /b 0
