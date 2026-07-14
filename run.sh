#!/bin/bash

echo "🚀 Starting CAS Assessment Service..."
echo ""
echo "📝 Form UI will be available at: http://localhost:8000"
echo "🔧 API endpoint: http://localhost:8000/v1/assess"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

cd "$(dirname "$0")"
uvicorn main:app --reload --host 0.0.0.0 --port 8000
