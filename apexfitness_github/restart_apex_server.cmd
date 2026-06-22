@echo off
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5002" ^| findstr "LISTENING"') do taskkill /PID %%a /F
cd /d C:\Users\lucas\Downloads\apexfitness\apexfitness
..\.venv\Scripts\python.exe app_unico.py
