@echo off
set "FLASK_APP=app.py"
set "FLASK_ENV=development"
".\test_venv\Scripts\python.exe" -m flask run --debug
