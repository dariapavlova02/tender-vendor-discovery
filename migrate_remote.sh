#!/bin/bash
# Remote migration script - runs inside Railway container

echo "🚀 Running migration inside Railway container..."
echo "📁 Uploading SQLite database..."

# Check if vendor_ai.db exists
if [ ! -f "vendor_ai.db" ]; then
    echo "❌ vendor_ai.db not found!"
    exit 1
fi

# Compress database
echo "📦 Compressing database..."
gzip -c vendor_ai.db > vendor_ai.db.gz

# Upload to temporary storage (you'll need to modify this)
echo "⬆️  Upload vendor_ai.db.gz to a temporary URL (Google Drive, Dropbox, etc.)"
echo "Then run migration inside Railway container"
