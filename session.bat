@echo off
echo Opening credentials file. Paste the new AWS block, then Save (Ctrl+S) and CLOSE Notepad.
notepad "%USERPROFILE%\.aws\credentials"
echo.
echo Activating venv and testing credentials...
call venv\Scripts\activate.bat
python -c "import boto3; print(boto3.client('sts').get_caller_identity())"
echo.
echo If you saw an Account number above, you are LIVE.
cmd /k