@echo off
rem Roda o app a partir do codigo-fonte usando o ambiente LOCAL .venv (nunca o Python global).
rem Dependencias so sao instaladas na primeira vez ou quando o arquivo de requisitos mudar
rem (compara com a copia guardada em .venv\.requisitos-instalados).
rem Usa requirements.lock (versoes fixas + hashes) se existir; senao requirements.txt.
setlocal
cd /d "%~dp0"
set "PY=.venv\Scripts\python.exe"
set "REQ=requirements.txt"
set "HASH="
if exist "requirements.lock" (
    set "REQ=requirements.lock"
    set "HASH=--require-hashes"
)

if not exist "%PY%" (
    echo Criando o ambiente local .venv - so na primeira vez...
    py -3 -m venv .venv 2>nul
    if not exist "%PY%" python -m venv .venv
)
if not exist "%PY%" (
    echo ERRO: Python 3.10+ nao encontrado. Instale de https://www.python.org/downloads/ e abra de novo.
    pause
    exit /b 1
)

fc /b "%REQ%" ".venv\.requisitos-instalados" >nul 2>&1
if errorlevel 1 (
    echo Instalando dependencias a partir de %REQ% - so quando mudam...
    "%PY%" -m pip install -q --disable-pip-version-check %HASH% -r "%REQ%"
    if errorlevel 1 (
        echo ERRO: falha ao instalar as dependencias. Verifique a internet e tente de novo.
        pause
        exit /b 1
    )
    copy /y "%REQ%" ".venv\.requisitos-instalados" >nul
)

"%PY%" main.py %*
