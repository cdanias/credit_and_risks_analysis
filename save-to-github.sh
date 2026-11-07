#!/bin/bash
set -euo pipefail

TIMESTAMP=$(date "+%Y-%m-%d %H:%M")

echo "🔄 Saving your work to GitHub..."

git add .

if git diff --cached --quiet; then
    echo "ℹ️ No local changes to commit. Pushing any unpushed commits..."
else
    git commit -m "Auto-save: $TIMESTAMP"
fi

git push

echo "✅ Done! Your work is saved to GitHub."
