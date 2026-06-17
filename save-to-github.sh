#!/bin/bash

TIMESTAMP=$(date "+%Y-%m-%d %H:%M")

echo "🔄 Saving your work to GitHub..."

git add .

git commit -m "Auto-save: $TIMESTAMP"

git push

echo "✅ Done! Your work is saved to GitHub."