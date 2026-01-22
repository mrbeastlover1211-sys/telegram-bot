#!/bin/bash

echo "🎮 Starting Gold Mining Bot Dashboard"
echo "======================================"
echo ""

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo "❌ DATABASE_URL is not set!"
    echo ""
    echo "Please set it first:"
    echo ""
    echo "export DATABASE_URL=\"postgresql://user:pass@host:port/db\""
    echo ""
    echo "Get your DATABASE_URL from:"
    echo "Railway → PostgreSQL service → Variables tab"
    echo ""
    exit 1
fi

echo "✅ DATABASE_URL is set"
echo ""

# Check if Python3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 is not installed"
    echo "Please run: ./setup_dashboard.sh first"
    exit 1
fi

echo "✅ Python3 found"
echo ""

# Check if Flask is installed
if ! python3 -c "import flask" 2>/dev/null; then
    echo "❌ Flask is not installed"
    echo "Please run: ./setup_dashboard.sh first"
    exit 1
fi

echo "✅ Flask installed"
echo ""

# Check if dashboard_api.py exists
if [ ! -f "dashboard_api.py" ]; then
    echo "❌ dashboard_api.py not found"
    echo "Please make sure you're in the correct directory"
    exit 1
fi

echo "✅ dashboard_api.py found"
echo ""
echo "🚀 Starting dashboard server..."
echo ""
echo "📊 Dashboard will be available at:"
echo "   http://localhost:5000"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""
echo "Starting in 3 seconds..."
sleep 3

# Start the dashboard
python3 dashboard_api.py
