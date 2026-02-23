@echo off
TITLE Telegram Bot de Transcricao
echo ======================================================
echo 🎙️ Iniciando MeEscutaMeTranscreveBot...
echo ======================================================
echo.
cd /d "%~dp0"

IF NOT EXIST .venv (
    echo [ERRO] Ambiente virtual (.venv) nao encontrado!
    echo Rodando instalacao inicial...
    python -m venv .venv
    .venv\Scripts\pip install -r requirements.txt
)

echo [OK] Verificando dependencias...
.venv\Scripts\python -m pip install -q -r requirements.txt

echo [OK] Bot Online! Mantenha esta janela aberta.
echo.
.venv\Scripts\python main.py
echo.
echo ======================================================
echo [AVISO] O bot foi encerrado.
pause
