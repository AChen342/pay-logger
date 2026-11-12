@echo off
rem Puts a "Pay Logger" icon on your Desktop that opens the app (dashboard.pyw).
rem Run it again if you ever move this folder.
powershell -NoProfile -ExecutionPolicy Bypass -Command "$d=[Environment]::GetFolderPath('Desktop'); $s=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $d 'Pay Logger.lnk')); $s.TargetPath='%~dp0dashboard.pyw'; $s.WorkingDirectory='%~dp0'; $s.IconLocation='%~dp0pay_logger.ico'; $s.Description='Open Pay Logger'; $s.Save()"
if errorlevel 1 (echo Could not create the shortcut.) else (echo Done - look for "Pay Logger" on your Desktop.)
pause
