@echo off
setlocal

set "PROJECT_DIR=%~dp0"
set "PYTHON=%PROJECT_DIR%.venv\Scripts\python.exe"
set "SCRIPT=%PROJECT_DIR%main.py"

cd /d "%PROJECT_DIR%"

if not exist "%PYTHON%" (
    set "PYTHON=%PROJECT_DIR%..\.venv\Scripts\python.exe"
)

if not exist "%PYTHON%" (
    echo ERRO: ambiente virtual nao encontrado.
    echo Crie um ambiente em "%PROJECT_DIR%.venv" ou "%PROJECT_DIR%..\.venv".
    pause
    exit /b 1
)

if not exist "%SCRIPT%" (
    echo ERRO: main.py nao encontrado.
    pause
    exit /b 1
)

echo Iniciando o FuteBot...
"%PYTHON%" -u "%SCRIPT%"
set "STATUS=%ERRORLEVEL%"

if not "%STATUS%"=="0" (
    echo.
    echo O bot foi encerrado com erro. Codigo: %STATUS%
)

pause
exit /b %STATUS%
