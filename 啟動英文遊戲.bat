@echo off
setlocal
set "PORT=8765"
set "ROOT=%~dp0"
cd /d "%ROOT%"
netstat -ano | findstr /R /C:":%PORT% .*LISTENING" >nul 2>&1
if errorlevel 1 (
  where py >nul 2>&1 && (start "Bright English Server" /min py -3 server.py) || (where python >nul 2>&1 && start "Bright English Server" /min python server.py)
  timeout /t 2 /nobreak >nul
)
start "" "http://localhost:%PORT%"
endlocal
