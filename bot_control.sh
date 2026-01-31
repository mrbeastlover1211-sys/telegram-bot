#!/bin/bash

# Bot Control Script for Railway
# Requires Railway CLI: https://docs.railway.app/develop/cli

echo "🤖 Telegram Bot Control"
echo "======================="
echo ""

# Check if Railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo "❌ Railway CLI is not installed!"
    echo ""
    echo "Install it with:"
    echo "  brew install railway"
    echo ""
    echo "Or visit: https://docs.railway.app/develop/cli"
    exit 1
fi

echo "What do you want to do?"
echo ""
echo "1) Start Bot (costs ~$0.46/month)"
echo "2) Stop Bot (costs $0)"
echo "3) Check Bot Status"
echo "4) Exit"
echo ""
read -p "Enter choice (1-4): " choice

case $choice in
    1)
        echo ""
        echo "🚀 Starting bot..."
        railway up --detach
        echo ""
        echo "✅ Bot is starting! Users can now message it."
        echo "💰 This will cost ~$0.46/month while running."
        ;;
    2)
        echo ""
        echo "🛑 Stopping bot..."
        railway down
        echo ""
        echo "✅ Bot stopped! No longer accepting messages."
        echo "💰 Cost: $0 while stopped."
        ;;
    3)
        echo ""
        echo "📊 Checking status..."
        railway status
        ;;
    4)
        echo "Goodbye!"
        exit 0
        ;;
    *)
        echo "❌ Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "Done!"
