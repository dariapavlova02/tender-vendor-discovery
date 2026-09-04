#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
exec poetry run streamlit run src/vendor_ai_agent/dashboard.py --server.address 127.0.0.1
