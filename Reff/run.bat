@echo off
echo Installing dependencies...
python -m pip install -r requirements.txt
echo.
echo Starting Employee Referral Portal...
python app.py
pause
