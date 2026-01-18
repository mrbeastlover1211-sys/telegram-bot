# Telegram Game Bot

A Telegram bot for a game with 5 selectable options.

## Features
- `/start` command shows welcome message with 5 options
- Inline keyboard buttons for user interaction
- Ready to deploy on Railway.app

## Deployment on Railway

1. Connect this GitHub repository to Railway
2. Add environment variable: `BOT_TOKEN` with your Telegram bot token
3. Railway will auto-deploy!

## Getting Bot Token

1. Open Telegram and search for `@BotFather`
2. Send `/newbot` command
3. Follow the instructions
4. Copy the bot token provided

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variable
export BOT_TOKEN="your_bot_token_here"

# Run the bot
python bot.py
```

## Environment Variables

- `BOT_TOKEN` - Your Telegram bot token from BotFather (required)
