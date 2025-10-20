#!/bin/bash

# Start FastAPI backend
echo "Starting FastAPI backend..."
cd /app/backend
python mist_with_api3.py &
BACKEND_PID=$!
sleep 10

# Start n8n from custom installation
echo "Starting n8n with external dependencies..."
cd /opt/n8n
npx n8n start --tunnel &
N8N_PID=$!

# Wait for n8n to be ready
sleep 20

# Start simple HTTP server for UI
echo "Starting UI server..."
cd /app/UI
python -m http.server 8080 &
UI_PID=$!

echo "=== All Services Running ==="
echo "Backend API: http://localhost:8000"
echo "n8n Interface: http://localhost:5678"
echo "UI: http://localhost:8080"
echo "============================="
echo "Workflow file: /app/workflow.json"
echo "Import this workflow in n8n interface"

# Wait for any process to exit
wait -n
exit $?
