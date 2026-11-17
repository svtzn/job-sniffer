@echo off
rem Job Sniffer - quick start for Windows.
rem First run: installs dependencies and Chromium, creates .env. Next runs: just starts the bot.

setlocal
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1

where uv >nul 2>nul
if errorlevel 1 goto :no_uv

echo [1/3] Syncing dependencies...
uv sync --quiet
if errorlevel 1 goto :fail

if exist "data\.chromium-installed" goto :env
echo [2/3] Installing Chromium for Playwright - first run only...
uv run playwright install chromium
if errorlevel 1 goto :fail
if not exist "data" mkdir "data"
type nul > "data\.chromium-installed"

:env
if exist ".env" goto :check_token
copy ".env.example" ".env" >nul
echo.
echo Created .env from .env.example.
echo Put your bot token into TELEGRAM_BOT_TOKEN, save the file and close Notepad.
notepad ".env"

:check_token
findstr /r /c:"^TELEGRAM_BOT_TOKEN=..*" ".env" >nul
if errorlevel 1 goto :no_token

echo [3/3] Starting the bot. Press Ctrl+C to stop.
echo.
uv run job-sniffer
echo.
echo Bot stopped.
pause
exit /b 0

:no_uv
echo uv is not installed. Install it with this PowerShell command, then reopen this window:
echo.
echo     powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 ^| iex"
echo.
pause
exit /b 1

:no_token
echo TELEGRAM_BOT_TOKEN is empty in .env - get a token from @BotFather and put it there.
notepad ".env"
pause
exit /b 1

:fail
echo.
echo Something went wrong, see the messages above.
pause
exit /b 1
