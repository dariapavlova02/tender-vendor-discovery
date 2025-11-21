#!/bin/bash

cd "$(dirname "$0")/.."

echo "🚀 Starting Tender AI Agent Dashboard..."
echo "📍 Dashboard will open at: http://localhost:8501"
echo ""

poetry run streamlit run src/vendor_ai_agent/dashboard.py
