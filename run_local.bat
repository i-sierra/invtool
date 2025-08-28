@echo off
setlocal enabledelayedexpansion
IF EXIST .env (
    for /f "usebackq tokens=1,* delims==" %%a in (.env) do (
        if not "%%a"=="" if not "%%a"=="" set %%a=%%b
    )
)
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --reload