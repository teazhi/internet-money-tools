#!/bin/bash

# Local Development Startup Script
echo "🚀 Starting builders+ Dashboard in Development Mode"
echo "================================================"
echo ""
echo "📋 This will start:"
echo "   • Backend (Flask) on http://localhost:5000"
echo "   • Frontend (React) on http://localhost:3000"
echo ""
echo "💡 To stop: Press Ctrl+C in both terminal windows"
echo ""
echo "Starting services..."
echo ""

# Function to start backend
start_backend() {
    echo "🔧 Starting Flask Backend..."
    cd dashboard/backend
    python3 app.py
}

# Function to start frontend  
start_frontend() {
    echo "⚛️  Starting React Frontend..."
    cd dashboard/frontend
    npm start
}

# Check if we should start both or just one
if [ "$1" = "backend" ]; then
    start_backend
elif [ "$1" = "frontend" ]; then
    start_frontend
else
    echo "🔄 Starting both services..."
    echo "📝 Open 2 terminal windows and run:"
    echo "   Terminal 1: ./start-local.sh backend"
    echo "   Terminal 2: ./start-local.sh frontend"
    echo ""
    echo "Or run them manually:"
    echo "   cd dashboard/backend && python3 app.py"
    echo "   cd dashboard/frontend && npm start"
fi