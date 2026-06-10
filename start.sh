#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

echo "============================================================"
echo " AutomatizacionV1 - Iniciando servidores (Linux)"
echo "============================================================"
echo

echo "[1/3] Instalando dependencias..."
pip install -r requirements.txt -q
echo

echo "[2/3] Iniciando FastAPI en http://localhost:8000 ..."
uvicorn api.app:app --host 0.0.0.0 --port 8000 --reload &
API_PID=$!
sleep 3

echo "[3/3] Iniciando Streamlit en http://localhost:8501 ..."
streamlit run dashboard.py --server.port 8501 --server.address 0.0.0.0 &
STREAMLIT_PID=$!

echo
echo "============================================================"
echo " Servidores activos:"
echo "   API:       http://localhost:8000/docs"
echo "   Dashboard: http://localhost:8501"
echo " Presiona Ctrl+C para detener ambos servidores."
echo "============================================================"

trap "kill $API_PID $STREAMLIT_PID 2>/dev/null; echo 'Servidores detenidos.'" INT TERM
wait $API_PID $STREAMLIT_PID
