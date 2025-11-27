#!/bin/bash
# Railway PostgreSQL Migration Script

if [ -z "$DATABASE_URL" ]; then
    echo "❌ ERROR: DATABASE_URL not set"
    echo ""
    echo "Please set DATABASE_URL from Railway:"
    echo "  1. Railway → Postgres service → Connect tab"
    echo "  2. Copy the DATABASE_URL"
    echo "  3. Run: export DATABASE_URL=\"postgresql://...\""
    echo "  4. Run this script again"
    exit 1
fi

echo "🚀 Starting migration from SQLite to PostgreSQL..."
echo ""
poetry run python scripts/migrate_sqlite_to_postgres.py
