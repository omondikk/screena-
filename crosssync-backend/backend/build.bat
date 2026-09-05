@echo off
echo Building CrossSync Clipboard...
pyinstaller --onefile --name CrossSync --console simple_desktop.py
echo Build complete! Find the executable in dist/
pause