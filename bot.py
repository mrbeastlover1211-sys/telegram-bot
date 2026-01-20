import os
import logging
import sqlite3
import json
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

# SQLite database connection
db_connection = None

# Store last user who messaged admin (for quick reply)
last_user_message = {}

def init_database():
    """Initialize SQLite database."""
    global db_connection
    
    try:
        # Create database file
        db_connection = sqlite3.connect('telegram_bot.db', check_same_thread=False)
        cursor = db_connection.cursor()
        
        # Create tickets table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tickets (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                closed_at TIMESTAMP
            )
        ''')
        
        # Create messages table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                text TEXT,
                time TEXT,
                from_user TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES tickets(user_id)
            )
        ''')
        
        # Create users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        db_connection.commit()
        logger.info("✅ SQLite database initialized successfully!")
        logger.info("💾 Database: telegram_bot.db (Ready to handle 10,000+ tickets!)")
        return True
    except Exception as e:
        logger.error(f"❌ Database initialization error: {e}")
        return False

def save_ticket(user_id, username, first_name, last_name=None, active=True):
    """Save or update a ticket in SQLite."""
    if not db_connection:
        return
    
    cursor = db_connection.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO tickets (user_id, username, first_name, last_name, active, last_updated)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    ''', (user_id, username, first_name, last_name, 1 if active else 0))
    db_connection.commit()

def add_message_to_ticket(user_id, message_text, from_user='user'):
    """Add a message to a ticket."""
    if not db_connection:
        return
    
    cursor = db_connection.cursor()
    time_now = datetime.now().strftime('%H:%M:%S')
    cursor.execute('''
        INSERT INTO messages (user_id, text, time, from_user)
        VALUES (?, ?, ?, ?)
    ''', (user_id, message_text, time_now, from_user))
    
    # Update ticket last_updated
    cursor.execute('''
        UPDATE tickets SET last_updated = CURRENT_TIMESTAMP WHERE user_id = ?
    ''', (user_id,))
    
    db_connection.commit()

def get_ticket(user_id):
    """Get a ticket from SQLite."""
    if not db_connection:
        return None
    
    cursor = db_connection.cursor()
    cursor.execute('''
        SELECT user_id, username, first_name, last_name, active, created_at, last_updated, closed_at
        FROM tickets WHERE user_id = ?
    ''', (user_id,))
    
    row = cursor.fetchone()
    if not row:
        return None
    
    # Get messages for this ticket
    cursor.execute('''
        SELECT text, time, from_user FROM messages WHERE user_id = ? ORDER BY created_at
    ''', (user_id,))
    messages = [{'text': msg[0], 'time': msg[1], 'from': msg[2]} for msg in cursor.fetchall()]
    
    return {
        'user_id': row[0],
        'username': row[1],
        'first_name': row[2],
        'last_name': row[3],
        'active': bool(row[4]),
        'created_at': row[5],
        'last_updated': row[6],
        'closed_at': row[7],
        'messages': messages
    }

def get_active_tickets():
    """Get all active tickets."""
    if not db_connection:
        return []
    
    cursor = db_connection.cursor()
    cursor.execute('''
        SELECT user_id, username, first_name, last_name, active, created_at, last_updated
        FROM tickets WHERE active = 1 ORDER BY last_updated DESC
    ''')
    
    tickets = []
    for row in cursor.fetchall():
        user_id = row[0]
        
        # Get messages for this ticket
        cursor.execute('''
            SELECT text, time, from_user FROM messages WHERE user_id = ? ORDER BY created_at
        ''', (user_id,))
        messages = [{'text': msg[0], 'time': msg[1], 'from': msg[2]} for msg in cursor.fetchall()]
        
        tickets.append({
            'user_id': user_id,
            'username': row[1],
            'first_name': row[2],
            'last_name': row[3],
            'active': bool(row[4]),
            'created_at': row[5],
            'last_updated': row[6],
            'messages': messages
        })
    
    return tickets

def close_ticket(user_id):
    """Close a ticket."""
    if not db_connection:
        return
    
    cursor = db_connection.cursor()
    cursor.execute('''
        UPDATE tickets SET active = 0, closed_at = CURRENT_TIMESTAMP WHERE user_id = ?
    ''', (user_id,))
    db_connection.commit()

def save_user(user_id, username, first_name, last_name=None):
    """Save user information."""
    if not db_connection:
        return
    
    cursor = db_connection.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO users (user_id, username, first_name, last_name, last_seen)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
    ''', (user_id, username, first_name, last_name))
    db_connection.commit()

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
    
    # Save user to database
    save_user(user.id, user.username, user.first_name, user.last_name)
    
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
    
    # Handle Quick Reply button
    if option.startswith('quick_reply_'):
        if user.id != ADMIN_ID:
            await query.answer("❌ Only admin can use this button", show_alert=True)
            return
        
        # Extract user ID from callback data
        target_user_id = int(option.replace('quick_reply_', ''))
        
        # Set this user as the active reply target
        last_user_message[ADMIN_ID] = target_user_id
        
        # Get user info from database
        ticket = get_ticket(target_user_id)
        user_name = ticket.get('first_name', 'User') if ticket else 'User'
        
        await query.answer("✅ Quick reply mode activated!", show_alert=False)
        await query.edit_message_reply_markup(reply_markup=None)  # Remove buttons
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"💬 Quick Reply Mode Activated\n\n"
                 f"Replying to: {user_name} (ID: {target_user_id})\n\n"
                 f"💡 Just type your message and send it!"
        )
        return
    
    # Handle Close Ticket button
    if option.startswith('close_ticket_'):
        if user.id != ADMIN_ID:
            await query.answer("❌ Only admin can use this button", show_alert=True)
            return
        
        # Extract user ID from callback data
        target_user_id = int(option.replace('close_ticket_', ''))
        
        # Check if ticket exists
        ticket = get_ticket(target_user_id)
        if not ticket:
            await query.answer("❌ Ticket not found", show_alert=True)
            return
        
        # Close the ticket in database
        close_ticket(target_user_id)
        
        # Notify user
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text="✅ Your support ticket has been closed.\n"
                     "Thank you for contacting us!\n\n"
                     "Type /start if you need help again."
            )
        except Exception as e:
            logger.error(f"Failed to notify user of ticket closure: {e}")
        
        await query.answer("✅ Ticket closed!", show_alert=True)
        await query.edit_message_text(
            text=f"🔒 TICKET CLOSED\n\n"
                 f"{query.message.text}\n\n"
                 f"✅ Closed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        return
    
    # Handle View History button
    if option.startswith('view_history_'):
        if user.id != ADMIN_ID:
            await query.answer("❌ Only admin can use this button", show_alert=True)
            return
        
        # Extract user ID from callback data
        target_user_id = int(option.replace('view_history_', ''))
        
        # Get ticket from database
        ticket = get_ticket(target_user_id)
        if not ticket:
            await query.answer("❌ Chat not found", show_alert=True)
            return
        
        messages = ticket.get('messages', [])
        
        if not messages:
            await query.answer("📭 No messages yet", show_alert=True)
            return
        
        # Build message history
        history = f"📜 Chat History - {ticket['first_name']}\n\n"
        for msg in messages[-10:]:  # Show last 10 messages
            sender = "👤 User" if msg['from'] == 'user' else "👨‍💼 You"
            history += f"{sender} ({msg['time']}): {msg['text']}\n\n"
        
        history += f"{'─' * 30}\n💬 Total: {len(messages)} messages"
        
        await query.answer()
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=history
        )
        return
    
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
        # Save ticket to database
        save_ticket(user.id, user.username, user.first_name, user.last_name, active=True)
        
        await query.edit_message_text(
            text='💬 Support Chat Activated!\n\n'
                 'You can now send messages and our team will respond.\n'
                 'Type /stop to end the conversation.'
        )
        
        # Create inline keyboard with Reply button for admin
        keyboard = [
            [InlineKeyboardButton("💬 Quick Reply", callback_data=f'quick_reply_{user.id}')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"🆕 NEW SUPPORT TICKET\n"
                 f"👤 {user.first_name} {user.last_name or ''}\n"
                 f"🆔 ID: {user.id}\n"
                 f"📱 @{user.username or 'No username'}\n\n"
                 f"🔹 Click button below to reply\n"
                 f"🔹 Or just type your message\n"
                 f"🔹 Or use: /reply {user.id} message",
            reply_markup=reply_markup
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
    ticket = get_ticket(user.id)
    if ticket and ticket.get('active', False):
        # Store message in database
        add_message_to_ticket(user.id, message_text, from_user='user')
        
        # Store as last user who messaged (for quick reply)
        if ADMIN_ID:
            last_user_message[ADMIN_ID] = user.id
        
        # Create inline keyboard with Reply button
        keyboard = [
            [InlineKeyboardButton("💬 Quick Reply", callback_data=f'quick_reply_{user.id}')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Forward to admin with reply button
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"💬 Message from {user.first_name} (ID: {user.id})\n"
                 f"📱 @{user.username or 'No username'}\n\n"
                 f"💭 \"{message_text}\"\n\n"
                 f"🔹 Click button below to reply\n"
                 f"🔹 Or just type your message (I'll send to last user)\n"
                 f"🔹 Or use: /reply {user.id} message",
            reply_markup=reply_markup
        )
        
        await update.message.reply_text(
            "✅ Message sent to support team!\n"
            "We'll respond shortly."
        )
    elif user.id == ADMIN_ID:
        # Admin is typing a message - check if replying to last user
        if ADMIN_ID in last_user_message and last_user_message[ADMIN_ID]:
            target_user_id = last_user_message[ADMIN_ID]
            
            # Check if this is a reply to bot's message
            if update.message.reply_to_message and update.message.reply_to_message.from_user.is_bot:
                # Admin is replying to a specific message - extract user ID from it
                replied_text = update.message.reply_to_message.text
                if "ID: " in replied_text:
                    try:
                        # Extract user ID from the message
                        import re
                        match = re.search(r'ID: (\d+)', replied_text)
                        if match:
                            target_user_id = int(match.group(1))
                    except:
                        pass
            
            # Send message to the target user
            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=f"💬 Support Team Response:\n\n{message_text}"
                )
                
                # Store in database
                add_message_to_ticket(target_user_id, message_text, from_user='admin')
                
                # Get ticket info
                ticket = get_ticket(target_user_id)
                user_name = ticket.get('first_name', 'User') if ticket else 'User'
                
                await update.message.reply_text(
                    f"✅ Message sent to user {target_user_id}!\n"
                    f"({user_name})"
                )
            except Exception as e:
                await update.message.reply_text(
                    f"❌ Failed to send message: {e}\n\n"
                    f"💡 Use /tickets to see active chats"
                )

# Admin command: View active tickets with action buttons
async def tickets_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show all active support tickets with quick action buttons (Admin only)."""
    user = update.effective_user
    
    if user.id != ADMIN_ID:
        await update.message.reply_text("❌ This command is only for admins.")
        return
    
    # Get active tickets from database
    active_tickets = get_active_tickets()
    
    if not active_tickets:
        await update.message.reply_text("📭 No active support tickets.")
        return
    
    await update.message.reply_text(f"📋 Found {len(active_tickets)} active ticket(s)...")
    
    # Show each ticket with action buttons
    for ticket in active_tickets:
        user_id = ticket['user_id']
        
        # Get last message from user
        messages = ticket.get('messages', [])
        user_messages = [msg for msg in messages if msg.get('from') == 'user']
        last_message = user_messages[-1]['text'] if user_messages else "No messages yet"
        last_message_preview = (last_message[:50] + '...') if len(last_message) > 50 else last_message
        
        # Create inline keyboard with action buttons
        keyboard = [
            [
                InlineKeyboardButton("💬 Reply", callback_data=f'quick_reply_{user_id}'),
                InlineKeyboardButton("🔒 Close", callback_data=f'close_ticket_{user_id}')
            ],
            [InlineKeyboardButton("📜 View History", callback_data=f'view_history_{user_id}')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        ticket_info = (
            f"🎫 Active Ticket\n\n"
            f"👤 {ticket['first_name']}\n"
            f"🆔 ID: {user_id}\n"
            f"📱 @{ticket.get('username') or 'No username'}\n"
            f"💬 Total Messages: {len(messages)}\n"
            f"📝 Last Message: \"{last_message_preview}\"\n"
            f"{'─' * 30}"
        )
        
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=ticket_info,
            reply_markup=reply_markup
        )

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
    ticket = get_ticket(target_user_id)
    if not ticket:
        await update.message.reply_text("❌ No active chat with this user.")
        return
    
    # Send message to user
    try:
        await context.bot.send_message(
            chat_id=target_user_id,
            text=f"💬 Support Team Response:\n\n{reply_text}"
        )
        
        # Store in database
        add_message_to_ticket(target_user_id, reply_text, from_user='admin')
        
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
    
    # Check if ticket exists
    ticket = get_ticket(target_user_id)
    if not ticket:
        await update.message.reply_text("❌ No chat found with this user.")
        return
    
    # Close the ticket
    close_ticket(target_user_id)
    
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
        f"({ticket['first_name']})"
    )

# User command: Stop support chat
async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """User can stop their support chat."""
    user = update.effective_user
    
    ticket = get_ticket(user.id)
    if ticket and ticket.get('active', False):
        close_ticket(user.id)
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
    
    if not db_connection:
        await update.message.reply_text("❌ Database not connected.")
        return
    
    # Get statistics from database
    cursor = db_connection.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM tickets")
    total_tickets = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM tickets WHERE active = 1")
    active_tickets = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM tickets WHERE active = 0")
    closed_tickets = cursor.fetchone()[0]
    
    message = (
        "📊 Bot Statistics\n\n"
        f"👥 Total Users: {total_users}\n"
        f"🎫 Total Tickets: {total_tickets}\n"
        f"✅ Active Tickets: {active_tickets}\n"
        f"🔒 Closed Tickets: {closed_tickets}\n"
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
    
    logger.info(f"✅ Bot token found (length: {len(token)} chars)")
    
    # Initialize Database
    if not init_database():
        logger.error("❌ Failed to initialize database. Bot will not start.")
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
