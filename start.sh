#!/bin/bash
set -e

echo "[$(date)] Starting AI Insem services..."

# Create necessary logs directories
mkdir -p logs/snapshots logs/incidents logs/heatmaps logs/reports

echo "[$(date)] Starting Flask API server on port 5000..."
python -u api_server.py &
API_PID=$!
echo "[$(date)] Flask API started with PID $API_PID"

# Give API time to start
sleep 3

echo "[$(date)] Starting Streamlit dashboard on port 8501..."
streamlit run dashboard.py \
  --server.port 8501 \
  --server.address 0.0.0.0 \
  --server.headless true \
  --logger.level=info &
STREAMLIT_PID=$!
echo "[$(date)] Streamlit started with PID $STREAMLIT_PID"

# Function to handle shutdown
shutdown() {
    echo "[$(date)] Shutting down services..."
    kill $API_PID $STREAMLIT_PID 2>/dev/null || true
    exit 0
}

# Trap signals
trap shutdown SIGTERM SIGINT

echo "[$(date)] All services started. Waiting for processes..."

# Wait for both processes
wait