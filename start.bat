@echo off
cd /d "%~dp0"
echo Starting clinic app in debug mode...
echo Access at http://127.0.0.1:8080
echo Close this window to stop the server.
start "" http://127.0.0.1:8080
python app.py
