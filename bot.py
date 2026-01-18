import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Start command handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message with 5 inline button options when the command /start is issued."""
    user = update.effective_user
    
    # Create inline keyboard with 5 options
    keyboard = [
        [InlineKeyboardButton("🎮 Option 1", callback_data='option_1')],
        [InlineKeyboardButton("🎯 Option 2", callback_data='option_2')],
        [InlineKeyboardButton("🎲 Option 3", callback_data='option_3')],
        [InlineKeyboardButton("🏆 Option 4", callback_data='option_4')],
        [InlineKeyboardButton("⚡ Option 5", callback_data='option_5')],
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f'👋 Welcome {user.first_name}!\n\n'
        f'🎮 Choose one of the options below to continue:',
        reply_markup=reply_markup
    )

# Button click handler
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button clicks from inline keyboard."""
    query = update.callback_query
    await query.answer()
    
    # Get which option was selected
    option = query.data
    
    # Response based on selection
    responses = {
        'option_1': '🎮 You selected Option 1!\n\nThis feature will be added soon.',
        'option_2': '🎯 You selected Option 2!\n\nThis feature will be added soon.',
        'option_3': '🎲 You selected Option 3!\n\nThis feature will be added soon.',
        'option_4': '🏆 You selected Option 4!\n\nThis feature will be added soon.',
        'option_5': '⚡ You selected Option 5!\n\nThis feature will be added soon.',
    }
    
    await query.edit_message_text(
        text=responses.get(option, 'Unknown option selected.')
    )

def main() -> None:
    """Start the bot."""
    # Get bot token from environment variable
    token = os.environ.get('BOT_TOKEN')
    
    if not token:
        logger.error("BOT_TOKEN environment variable not set!")
        return
    
    # Create the Application
    application = Application.builder().token(token).build()
    
    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Start the bot
    logger.info("Bot is starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
