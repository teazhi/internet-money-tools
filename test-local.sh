#!/bin/bash

# Test Local Development Environment
echo "🧪 Testing Local Development Setup"
echo "=================================="
echo ""

# Test backend startup
echo "🔧 Testing Backend..."
cd dashboard/backend
python3 -c "from app import app; print('✅ Backend imports successfully')" && echo "✅ Flask app loads correctly" || echo "❌ Backend has issues"
echo ""

# Test frontend setup
echo "⚛️  Testing Frontend..."
cd ../frontend
if [ -f "package.json" ]; then
    echo "✅ package.json found"
else
    echo "❌ package.json missing"
fi

if [ -f ".env.local" ]; then
    echo "✅ .env.local configured"
else
    echo "❌ .env.local missing"
fi

if [ -d "node_modules" ]; then
    echo "✅ Node modules installed"
else
    echo "❌ Run 'npm install' first"
fi

echo ""
echo "🎉 Setup complete! To start development:"
echo ""
echo "🖥️  Terminal 1 (Backend):"
echo "   cd dashboard/backend && python3 app.py"
echo ""
echo "🌐 Terminal 2 (Frontend):"
echo "   cd dashboard/frontend && npm start"
echo ""
echo "🔗 Then open: http://localhost:3000"