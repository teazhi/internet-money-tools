#!/bin/bash

# Fast build script for development
echo "🚀 Starting optimized build..."

# Use optimized requirements for faster installs
echo "📦 Installing production dependencies..."
pip install --upgrade pip setuptools wheel
pip install --no-cache-dir -r requirements.txt

# Install dev dependencies only if needed
if [ "$1" = "--dev" ]; then
    echo "🔧 Installing development dependencies..."
    pip install --no-cache-dir -r requirements-dev.txt
fi

echo "✅ Build complete!"
echo "🎯 Start the app with: python app.py"