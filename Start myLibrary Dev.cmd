@echo off
rem myLibrary for development: choose Personal Libraries or Test & Demo, then a library.
rem 开发用启动器：先选书库模式 (Library Mode)，再选书库 (library). Needs uv (winget install astral-sh.uv).
rem The ready-to-use package has its own launcher (package/); this one is for a source checkout.
chcp 65001 >nul
cd /d "%~dp0"
uv run scripts/launch_library.py %*
if errorlevel 1 pause
