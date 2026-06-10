@echo off
cd /d "%~dp0"
echo ============================================================
echo  AutomatizacionV1 - Iniciando servidores
echo ============================================================
echo.
echo [1/3] Instalando dependencias API...
py -3 -m pip install -r requirements_api.txt -q
echo.
echo [2/3] Iniciando FastAPI en http://localhost:8000 ...
start "FastAPI - AutomatizacionV1" cmd /k "py -3 -m uvicorn api.app:app --port 8000 --reload"
timeout /t 3 /nobreak >nul
echo.
echo [3/3] Iniciando Streamlit en http://localhost:8501 ...
start "Streamlit - AutomatizacionV1" cmd /k "py -3 -m streamlit run dashboard.py --server.port 8501"
timeout /t 2 /nobreak >nul
start http://localhost:8501
echo.
echo Servidores activos:
echo   API:       http://localhost:8000/docs
echo   Dashboard: http://localhost:8501
echo.
pause
