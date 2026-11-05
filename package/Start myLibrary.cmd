@echo off
rem Starts myLibrary (no console window stays open). The first start also creates
rem "myLibrary" shortcuts on the Desktop and in the Start menu; use those from then on.
start "" "%~dp0runtime\python\pythonw.exe" "%~dp0launch.py"
