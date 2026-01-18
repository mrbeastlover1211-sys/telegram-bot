import os
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Admin configuration - SET YOUR ADMIN TELEGRAM USER ID HERE
ADMIN_ID = None  # Will be set from environment variable

# Store active support chats: {user_id: {'username': str, 'first_name': str, 'active': bool, 'messages': []}}
active_chats = {}

# Helper function to notify admin
async def notify_admin(context: ContextTypes.DEFAULT_TYPE, message: str):
    """Send notification to admin."""
    if ADMIN_ID:
        try:
            await context.bot.send_message(chat_id=ADMIN_ID, text=message)
        except Exception as e:
            logger.error(f"Failed to notify admin: {e}")

# Start command handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message with 5 inline button options when the command /start is issued."""
    user = update.effective_user
    
    # Log user ID for debugging
    logger.info(f"User {user.first_name} (ID: {user.id}) started the bot")
    
    # Notify admin of new user
    await notify_admin(
        context,
        f"🆕 New User Started Bot\n"
        f"👤 Name: {user.first_name} {user.last_name or ''}\n"
        f"🆔 ID: {user.id}\n"
        f"📱 Username: @{user.username or 'No username'}\n"
        f"🕐 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    
    # Show user their ID if admin not set
    if not ADMIN_ID:
        await update.message.reply_text(
            f"⚠️ Admin not configured yet!\n\n"
            f"Your User ID: {user.id}\n\n"
            f"If you're the admin, add this ID to Railway as ADMIN_ID variable."
        )
    
    # Create inline keyboard with 5 options + Contact Support
    keyboard = [
        [InlineKeyboardButton("🎮 Option 1", callback_data='option_1')],
        [InlineKeyboardButton("🎯 Option 2", callback_data='option_2')],
        [InlineKeyboardButton("🎲 Option 3", callback_data='option_3')],
        [InlineKeyboardButton("🏆 Option 4", callback_data='option_4')],
        [InlineKeyboardButton("⚡ Option 5", callback_data='option_5')],
        [InlineKeyboardButton("💬 Contact Support", callback_data='contact_support')],
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
    
    user = query.from_user
    option = query.data
    
    # Notify admin of user's selection
    await notify_admin(
        context,
        f"🔔 User Action\n"
        f"👤 {user.first_name} (@{user.username or 'no username'})\n"
        f"🆔 ID: {user.id}\n"
        f"✨ Selected: {option.replace('_', ' ').title()}\n"
        f"🕐 {datetime.now().strftime('%H:%M:%S')}"
    )
    
    # Handle contact support
    if option == 'contact_support':
        active_chats[user.id] = {
            'username': user.username,
            'first_name': user.first_name,
            'active': True,
            'messages': []
        }
        
        await query.edit_message_text(
            text='💬 Support Chat Activated!\n\n'
                 'You can now send messages and our team will respond.\n'
                 'Type /stop to end the conversation.'
        )
        
        await notify_admin(
            context,
            f"🆕 NEW SUPPORT TICKET\n"
            f"👤 {user.first_name} {user.last_name or ''}\n"
            f"🆔 ID: {user.id}\n"
            f"📱 @{user.username or 'No username'}\n\n"
            f"💡 Reply with: /reply {user.id} your message"
        )
        return
    
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

# Handle user messages in support chat
async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle messages from users in active support chats."""
    user = update.effective_user
    message_text = update.message.text
    
    # Check if user has active support chat
    if user.id in active_chats and active_chats[user.id]['active']:
        # Store message
        active_chats[user.id]['messages'].append({
            'text': message_text,
            'time': datetime.now().strftime('%H:%M:%S'),
            'from': 'user'
        })
        
        # Forward to admin
        await notify_admin(
            context,
            f"💬 Message from {user.first_name} (ID: {user.id})\n"
            f"📱 @{user.username or 'No username'}\n\n"
            f"💭 \"{message_text}\"\n\n"
            f"💡 Reply: /reply {user.id} your_message"
        )
        
        await update.message.reply_text(
            "✅ Message sent to support team!\n"
            "We'll respond shortly."
        )
    elif user.id == ADMIN_ID:
        # Admin sent a message without using /reply command
        await update.message.reply_text(
            "💡 Use /reply <user_id> <message> to respond to users\n"
            "Or use /tickets to see all active support tickets"
        )

# Admin command: View active tickets
async def tickets_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show all active support tickets (Admin only)."""
    user = update.effective_user
    
    if user.id != ADMIN_ID:
        await update.message.reply_text("❌ This command is only for admins.")
        return
    
    if not active_chats:
        await update.message.reply_text("📭 No active support tickets.")
        return
    
    message = "🎫 Active Support Tickets:\n\n"
    for user_id, chat_data in active_chats.items():
        if chat_data['active']:
            message += (
                f"👤 {chat_data['first_name']}\n"
                f"🆔 ID: {user_id}\n"
                f"📱 @{chat_data['username'] or 'No username'}\n"
                f"💬 Messages: {len(chat_data['messages'])}\n"
                f"⚡ Reply: /reply {user_id} message\n"
                f"🔒 Close: /close {user_id}\n"
                f"{'─' * 30}\n"
            )
    
    await update.message.reply_text(message)

# Admin command: Reply to user
async def reply_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reply to a user's message (Admin only)."""
    user = update.effective_user
    
    if user.id != ADMIN_ID:
        await update.message.reply_text("❌ This command is only for admins.")
        return
    
    # Parse command: /reply <user_id> <message>
    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Usage: /reply <user_id> <message>\n"
            "Example: /reply 123456789 Hello, how can I help?"
        )
        return
    
    try:
        target_user_id = int(context.args[0])
        reply_text = ' '.join(context.args[1:])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID. Must be a number.")
        return
    
    # Check if chat exists
    if target_user_id not in active_chats:
        await update.message.reply_text("❌ No active chat with this user.")
        return
    
    # Send message to user
    try:
        await context.bot.send_message(
            chat_id=target_user_id,
            text=f"💬 Support Team Response:\n\n{reply_text}"
        )
        
        # Store in chat history
        active_chats[target_user_id]['messages'].append({
            'text': reply_text,
            'time': datetime.now().strftime('%H:%M:%S'),
            'from': 'admin'
        })
        
        await update.message.reply_text(f"✅ Message sent to user {target_user_id}!")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to send message: {e}")

# Admin command: Close ticket
async def close_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Close a support ticket (Admin only)."""
    user = update.effective_user
    
    if user.id != ADMIN_ID:
        await update.message.reply_text("❌ This command is only for admins.")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text(
            "❌ Usage: /close <user_id>\n"
            "Example: /close 123456789"
        )
        return
    
    try:
        target_user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID. Must be a number.")
        return
    
    if target_user_id not in active_chats:
        await update.message.reply_text("❌ No chat found with this user.")
        return
    
    # Close the ticket
    active_chats[target_user_id]['active'] = False
    
    # Notify user
    try:
        await context.bot.send_message(
            chat_id=target_user_id,
            text="✅ Support ticket has been closed.\n"
                 "Thank you for contacting us!\n\n"
                 "Type /start to return to the main menu."
        )
    except Exception as e:
        logger.error(f"Failed to notify user of ticket closure: {e}")
    
    await update.message.reply_text(
        f"✅ Ticket closed for user {target_user_id}\n"
        f"({active_chats[target_user_id]['first_name']})"
    )

# User command: Stop support chat
async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """User can stop their support chat."""
    user = update.effective_user
    
    if user.id in active_chats and active_chats[user.id]['active']:
        active_chats[user.id]['active'] = False
        await update.message.reply_text(
            "✅ Support chat ended.\n"
            "Type /start to return to the main menu."
        )
        
        await notify_admin(
            context,
            f"🔚 User ended support chat\n"
            f"👤 {user.first_name} (ID: {user.id})"
        )
    else:
        await update.message.reply_text("You don't have an active support chat.")

# Admin command: Get stats
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show bot statistics (Admin only)."""
    user = update.effective_user
    
    if user.id != ADMIN_ID:
        await update.message.reply_text("❌ This command is only for admins.")
        return
    
    total_chats = len(active_chats)
    active_tickets = sum(1 for chat in active_chats.values() if chat['active'])
    closed_tickets = total_chats - active_tickets
    
    message = (
        "📊 Bot Statistics\n\n"
        f"👥 Total Users: {total_chats}\n"
        f"🎫 Active Tickets: {active_tickets}\n"
        f"✅ Closed Tickets: {closed_tickets}\n"
    )
    
    await update.message.reply_text(message)

# Command to get your own user ID
async def myid_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the user their Telegram ID."""
    user = update.effective_user
    
    message = (
        f"👤 Your Telegram Info:\n\n"
        f"🆔 User ID: `{user.id}`\n"
        f"📱 Username: @{user.username or 'No username'}\n"
        f"👋 Name: {user.first_name} {user.last_name or ''}\n\n"
        f"💡 Copy your User ID and add it to Railway as ADMIN_ID"
    )
    
    await update.message.reply_text(message, parse_mode='Markdown')

def main() -> None:
    """Start the bot."""
    global ADMIN_ID
    
    # Get bot token from environment variable
    token = os.environ.get('BOT_TOKEN')
    
    if not token:
        logger.error("❌ BOT_TOKEN environment variable not set!")
        logger.error("Please add BOT_TOKEN to Railway environment variables")
        return
    
    # Get admin ID from environment variable
    admin_id_str = os.environ.get('ADMIN_ID')
    if admin_id_str:
        try:
            ADMIN_ID = int(admin_id_str)
            logger.info(f"✅ Admin ID set: {ADMIN_ID}")
        except ValueError:
            logger.error("❌ ADMIN_ID must be a number!")
    else:
        logger.warning("⚠️ ADMIN_ID not set - admin features will be disabled")
        logger.warning("To enable admin features, add ADMIN_ID environment variable")
    
    logger.info(f"✅ Bot token found (length: {len(token)} chars)")
    
    # Create the Application
    try:
        application = Application.builder().token(token).build()
        logger.info("✅ Application built successfully")
    except Exception as e:
        logger.error(f"❌ Failed to build application: {e}")
        return
    
    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stop", stop_command))
    application.add_handler(CommandHandler("myid", myid_command))
    application.add_handler(CommandHandler("tickets", tickets_command))
    application.add_handler(CommandHandler("reply", reply_command))
    application.add_handler(CommandHandler("close", close_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_message))
    logger.info("✅ Handlers registered")
    
    # Start the bot
    logger.info("🚀 Bot is starting polling...")
    logger.info("📋 Available commands:")
    logger.info("   User: /start, /stop")
    logger.info("   Admin: /tickets, /reply, /close, /stats")
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logger.error(f"❌ Error running bot: {e}")

if __name__ == '__main__':
    main()
