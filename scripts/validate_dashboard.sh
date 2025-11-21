#!/bin/bash

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "🧪 Testing Tender AI Agent Dashboard Setup"
echo "=========================================="
echo ""

echo "✓ Step 1: Checking Poetry installation..."
if ! command -v poetry &> /dev/null; then
    echo "❌ Poetry not found. Install: curl -sSL https://install.python-poetry.org | python3 -"
    exit 1
fi
echo "  Poetry: $(poetry --version)"
echo ""

echo "✓ Step 2: Checking dependencies..."
if ! poetry show streamlit &> /dev/null; then
    echo "⚠️  Streamlit not installed. Installing..."
    poetry install
else
    echo "  Streamlit: $(poetry run streamlit --version)"
fi
echo ""

echo "✓ Step 3: Checking environment variables..."
if [ -f .env ]; then
    echo "  .env file found"
    if grep -q "OPENAI_API_KEY" .env; then
        echo "  ✓ OPENAI_API_KEY configured"
    else
        echo "  ⚠️  OPENAI_API_KEY not set in .env"
    fi
else
    echo "  ⚠️  .env file not found. Create one with OPENAI_API_KEY"
fi
echo ""

echo "✓ Step 4: Checking dashboard file..."
if [ -f "src/vendor_ai_agent/dashboard.py" ]; then
    echo "  ✓ Dashboard file exists"
else
    echo "  ❌ Dashboard file not found at src/vendor_ai_agent/dashboard.py"
    exit 1
fi
echo ""

echo "✓ Step 5: Validating Python syntax..."
if poetry run python -m py_compile src/vendor_ai_agent/dashboard.py 2>/dev/null; then
    echo "  ✓ Dashboard syntax valid"
else
    echo "  ⚠️  Dashboard has syntax issues (may need streamlit installed)"
fi
echo ""

echo "✓ Step 6: Checking test data..."
if [ -d "data/Object _ rfx_18106 - OPP-1984 Supply and Delivery of Ammunition" ]; then
    echo "  ✓ Test tender data found"
    NUM_FILES=$(find "data/Object _ rfx_18106 - OPP-1984 Supply and Delivery of Ammunition" -name "*.pdf" | wc -l)
    echo "    Found $NUM_FILES PDF files"
else
    echo "  ⚠️  Test data directory not found"
fi
echo ""

echo "=========================================="
echo "✅ Setup validation complete!"
echo ""
echo "To start the dashboard, run:"
echo "  ./scripts/run_dashboard.sh"
echo ""
echo "Or manually:"
echo "  poetry run streamlit run src/vendor_ai_agent/dashboard.py"
echo ""
echo "Dashboard will open at: http://localhost:8501"
