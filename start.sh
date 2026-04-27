#!/bin/bash

# Start Flask API server in background
python api_server.py &

# Start Streamlit dashboard
streamlit run dashboard.py --server.port 8501 --server.address 0.0.0.0 --server.headless true