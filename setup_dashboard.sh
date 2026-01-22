#!/bin/bash

echo "🚀 Dashboard Setup Script"
echo "=========================="
echo ""

# Step 1: Check if Python3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 is not installed. Please install it first:"
    echo "   brew install python3"
    exit 1
fi

echo "✅ Python3 is installed"
echo ""

# Step 2: Install dependencies
echo "📦 Installing dependencies..."
pip3 install flask flask-cors psycopg2-binary python-telegram-bot

if [ $? -eq 0 ]; then
    echo "✅ Dependencies installed successfully"
else
    echo "❌ Failed to install dependencies"
    exit 1
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "📝 NEXT STEP:"
echo "You need to set your DATABASE_URL"
echo ""
echo "1. Go to Railway.app"
echo "2. Click your PostgreSQL service"
echo "3. Click 'Variables' tab"
echo "4. Copy the DATABASE_URL value"
echo ""
echo "Then run this command (replace with your actual URL):"
echo ""
echo "export DATABASE_URL=\"your_database_url_here\""
echo ""
echo "Then run:"
echo "python3 dashboard_api.py"
echo ""
echo "And open: http://localhost:5000"
echo ""
