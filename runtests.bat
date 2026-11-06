@echo off
cd /d "%~dp0"
python manage.py test expenses -v 2
pause