import os
import logging
import json
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import pool

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Admin configuration - SET YOUR ADMIN TELEGRAM USER ID HERE
ADMIN_ID = None  # Will be set from environment variable

# PostgreSQL connection pool
db_pool = None

# Store last user who messaged admin (for quick reply)
last_user_message = {}

# Store pagination state for each admin: {admin_id: {'page': int, 'filter': str}}
pagination_state = {}

# Store conversation state for users: {user_id: {'state': str, 'data': {}, 'option': str}}
conversation_states = {}

def init_database():
    """Initialize PostgreSQL connection."""
    global db_pool
    
    # Railway automatically sets DATABASE_URL when you add PostgreSQL
    database_url = os.environ.get('DATABASE_URL')
    
    if not database_url:
        logger.error("❌ DATABASE_URL environment variable not set!")
        logger.error("Please add PostgreSQL database in Railway")
        return False
    
    try:
        # Create connection pool
        db_pool = pool.SimpleConnectionPool(
            1, 10,
            database_url
        )
        
        # Test connection and create tables
        conn = db_pool.getconn()
        cursor = conn.cursor()
        
        # Create tickets table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tickets (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                closed_at TIMESTAMP,
                messages JSONB DEFAULT '[]'::jsonb
            )
        ''')
        
        # Create users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_tickets_active ON tickets(active)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_tickets_updated ON tickets(last_updated DESC)')
        
        conn.commit()
        cursor.close()
        db_pool.putconn(conn)
        
        logger.info("✅ PostgreSQL connected successfully!")
        logger.info("💾 Database: Ready to handle 100,000+ tickets!")
        return True
    except Exception as e:
        logger.error(f"❌ PostgreSQL initialization error: {e}")
        return False

def save_ticket(user_id, username, first_name, last_name=None, active=True):
    """Save or update a ticket in PostgreSQL."""
    if not db_pool:
        return
    
    conn = db_pool.getconn()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO tickets (user_id, username, first_name, last_name, active, last_updated)
            VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id) DO UPDATE SET
                username = EXCLUDED.username,
                first_name = EXCLUDED.first_name,
                last_name = EXCLUDED.last_name,
                active = EXCLUDED.active,
                last_updated = CURRENT_TIMESTAMP
        ''', (user_id, username, first_name, last_name, active))
        conn.commit()
        cursor.close()
    finally:
        db_pool.putconn(conn)

def add_message_to_ticket(user_id, message_text, from_user='user'):
    """Add a message to a ticket."""
    if not db_pool:
        return
    
    conn = db_pool.getconn()
    try:
        cursor = conn.cursor()
        time_now = datetime.utcnow().strftime('%H:%M:%S')
        message_obj = json.dumps({'text': message_text, 'time': time_now, 'from': from_user})
        
        cursor.execute('''
            UPDATE tickets 
            SET messages = messages || %s::jsonb,
                last_updated = CURRENT_TIMESTAMP
            WHERE user_id = %s
        ''', (message_obj, user_id))
        conn.commit()
        cursor.close()
    finally:
        db_pool.putconn(conn)

def get_ticket(user_id):
    """Get a ticket from PostgreSQL."""
    if not db_pool:
        return None
    
    conn = db_pool.getconn()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute('''
            SELECT user_id, username, first_name, last_name, active, 
                   created_at, last_updated, closed_at, messages
            FROM tickets WHERE user_id = %s
        ''', (user_id,))
        ticket = cursor.fetchone()
        cursor.close()
        return dict(ticket) if ticket else None
    finally:
        db_pool.putconn(conn)

def get_active_tickets():
    """Get all active tickets."""
    if not db_pool:
        return []
    
    conn = db_pool.getconn()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute('''
            SELECT user_id, username, first_name, last_name, active,
                   created_at, last_updated, messages
            FROM tickets WHERE active = TRUE
            ORDER BY last_updated DESC
        ''')
        tickets = cursor.fetchall()
        cursor.close()
        return [dict(t) for t in tickets]
    finally:
        db_pool.putconn(conn)

def close_ticket(user_id):
    """Close a ticket."""
    if not db_pool:
        return
    
    conn = db_pool.getconn()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE tickets 
            SET active = FALSE, closed_at = CURRENT_TIMESTAMP
            WHERE user_id = %s
        ''', (user_id,))
        conn.commit()
        cursor.close()
    finally:
        db_pool.putconn(conn)

def save_user(user_id, username, first_name, last_name=None):
    """Save user information."""
    if not db_pool:
        return
    
    conn = db_pool.getconn()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (user_id, username, first_name, last_name, last_seen)
            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id) DO UPDATE SET
                username = EXCLUDED.username,
                first_name = EXCLUDED.first_name,
                last_name = EXCLUDED.last_name,
                last_seen = CURRENT_TIMESTAMP
        ''', (user_id, username, first_name, last_name))
        conn.commit()
        cursor.close()
    finally:
        db_pool.putconn(conn)

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
    
    # Check if user is admin
    is_admin = (user.id == ADMIN_ID)
    
    # Notify admin of new user (if not the admin themselves)
    if not is_admin:
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
        return
    
    # Admin gets special admin panel
    if is_admin:
        keyboard = [
            [InlineKeyboardButton("🎫 Active Tickets", callback_data='admin_tickets')],
            [InlineKeyboardButton("🚀 Quick Close Dashboard", callback_data='admin_quick_close')],
            [InlineKeyboardButton("📊 Statistics", callback_data='admin_stats')],
            [InlineKeyboardButton("👥 All Users", callback_data='admin_users')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f'👨‍💼 Admin Panel\n\n'
            f'Welcome back, {user.first_name}!\n'
            f'Choose an action below:',
            reply_markup=reply_markup
        )
    else:
        # Clear any existing conversation state
        if user.id in conversation_states:
            del conversation_states[user.id]
        
        # Regular users get normal menu
        keyboard = [
            [InlineKeyboardButton("💰 5000 Gold for X Post", callback_data='option_1')],
            [InlineKeyboardButton("🎁 Promoters Reward", callback_data='option_2')],
            [InlineKeyboardButton("👥 Refer and Earn Reward", callback_data='option_3')],
            [InlineKeyboardButton("⛏️ Picaxe Issue", callback_data='option_4')],
            [InlineKeyboardButton("💳 Wallet Issue", callback_data='option_5')],
            [InlineKeyboardButton("💬 Contact Support", callback_data='contact_support')],
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f'👋 Welcome to Gold Mining Bot, {user.first_name}!\n\n'
            f'🎮 Choose an option below:',
            reply_markup=reply_markup
        )

# Button click handler
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button clicks from inline keyboard."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    option = query.data
    
    # Handle Admin Panel buttons
    if option == 'admin_tickets':
        if user.id != ADMIN_ID:
            await query.answer("❌ Only admin can use this", show_alert=True)
            return
        
        await query.answer("Loading tickets...", show_alert=False)
        
        # Get active tickets from database
        active_tickets = get_active_tickets()
        
        if not active_tickets:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text="📭 No active support tickets."
            )
            return
        
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"📋 Found {len(active_tickets)} active ticket(s)..."
        )
        
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
        return
    
    if option == 'admin_stats':
        if user.id != ADMIN_ID:
            await query.answer("❌ Only admin can use this", show_alert=True)
            return
        
        await query.answer("Loading statistics...", show_alert=False)
        
        if not db_pool:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text="❌ Database not connected."
            )
            return
        
        conn = db_pool.getconn()
        try:
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM tickets")
            total_tickets = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM tickets WHERE active = TRUE")
            active_tickets = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM tickets WHERE active = FALSE")
            closed_tickets = cursor.fetchone()[0]
            
            cursor.close()
            
            message = (
                "📊 Bot Statistics\n\n"
                f"👥 Total Users: {total_users}\n"
                f"🎫 Total Tickets: {total_tickets}\n"
                f"✅ Active Tickets: {active_tickets}\n"
                f"🔒 Closed Tickets: {closed_tickets}\n"
            )
            
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=message
            )
        finally:
            db_pool.putconn(conn)
        return
    
    if option == 'admin_users':
        if user.id != ADMIN_ID:
            await query.answer("❌ Only admin can use this", show_alert=True)
            return
        
        await query.answer()
        
        # Get all users from database
        if not db_pool:
            await query.message.reply_text("❌ Database not connected.")
            return
        
        conn = db_pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute('''
                SELECT user_id, username, first_name, last_name, 
                       joined_at, last_seen
                FROM users
                ORDER BY last_seen DESC
                LIMIT 20
            ''')
            users = cursor.fetchall()
            cursor.close()
            
            if not users:
                await query.message.reply_text("📭 No users found.")
                return
            
            message = f"👥 Recent Users (Last 20)\n\n"
            for u in users:
                message += (
                    f"👤 {u['first_name']} {u.get('last_name') or ''}\n"
                    f"🆔 ID: {u['user_id']}\n"
                    f"📱 @{u.get('username') or 'No username'}\n"
                    f"🕐 Last seen: {u['last_seen'].strftime('%Y-%m-%d %H:%M') if u.get('last_seen') else 'Never'}\n"
                    f"{'─' * 25}\n"
                )
            
            await context.bot.send_message(chat_id=ADMIN_ID, text=message)
        finally:
            db_pool.putconn(conn)
        return
    
    # Handle Quick Close Dashboard with pagination
    if option.startswith('admin_quick_close'):
        if user.id != ADMIN_ID:
            await query.answer("❌ Only admin can use this", show_alert=True)
            return
        
        # Extract page number from callback data
        page = 1
        filter_type = 'all'
        
        if '_page_' in option:
            parts = option.split('_page_')
            page = int(parts[1].split('_')[0])
            if '_filter_' in option:
                filter_type = parts[1].split('_filter_')[1]
        elif '_filter_' in option:
            filter_type = option.split('_filter_')[1]
        
        await query.answer("Loading dashboard...", show_alert=False)
        
        # Get active tickets from database
        all_tickets = get_active_tickets()
        
        if not all_tickets:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text="📭 No open tickets! All clear! ✅"
            )
            return
        
        # Apply filters
        filtered_tickets = all_tickets
        filter_label = "All Tickets"
        
        if filter_type == 'today':
            from datetime import datetime, timedelta
            today = datetime.utcnow().date()
            filtered_tickets = [t for t in all_tickets if t.get('created_at') and t['created_at'].date() == today]
            filter_label = "Today's Tickets"
        elif filter_type == 'urgent':
            filtered_tickets = [t for t in all_tickets if len(t.get('messages', [])) >= 5]
            filter_label = "Urgent (5+ messages)"
        elif filter_type == 'recent':
            filtered_tickets = all_tickets[:20]
            filter_label = "20 Most Recent"
        
        if not filtered_tickets:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"📭 No tickets match filter: {filter_label}"
            )
            return
        
        # Pagination
        per_page = 10
        total_pages = (len(filtered_tickets) + per_page - 1) // per_page
        page = max(1, min(page, total_pages))
        
        start_idx = (page - 1) * per_page
        end_idx = min(start_idx + per_page, len(filtered_tickets))
        page_tickets = filtered_tickets[start_idx:end_idx]
        
        # Build message
        message = f"🚀 Quick Close Dashboard\n\n"
        message += f"📊 {len(filtered_tickets)} Ticket(s) | Filter: {filter_label}\n"
        message += f"📄 Page {page}/{total_pages}\n"
        message += f"{'═' * 30}\n\n"
        
        keyboard = []
        
        for ticket in page_tickets:
            user_id = ticket['user_id']
            first_name = ticket['first_name']
            username = ticket.get('username', 'no_username')
            messages = ticket.get('messages', [])
            msg_count = len(messages)
            
            user_messages = [msg for msg in messages if msg.get('from') == 'user']
            last_msg = user_messages[-1]['text'][:30] + '...' if user_messages and len(user_messages[-1]['text']) > 30 else (user_messages[-1]['text'] if user_messages else "No messages")
            
            message += f"👤 {first_name} (@{username})\n"
            message += f"   💬 {msg_count} msgs | Last: \"{last_msg}\"\n\n"
            
            keyboard.append([
                InlineKeyboardButton(
                    f"✅ Close {first_name}'s Ticket", 
                    callback_data=f'quick_close_{user_id}'
                )
            ])
        
        # Pagination buttons
        nav_buttons = []
        if page > 1:
            nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f'admin_quick_close_page_{page-1}_filter_{filter_type}'))
        nav_buttons.append(InlineKeyboardButton(f"📄 {page}/{total_pages}", callback_data='noop'))
        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f'admin_quick_close_page_{page+1}_filter_{filter_type}'))
        
        if len(nav_buttons) > 1:
            keyboard.append(nav_buttons)
        
        # Filter buttons
        keyboard.append([
            InlineKeyboardButton("🔍 All", callback_data='admin_quick_close_filter_all'),
            InlineKeyboardButton("📅 Today", callback_data='admin_quick_close_filter_today'),
        ])
        keyboard.append([
            InlineKeyboardButton("🔥 Urgent", callback_data='admin_quick_close_filter_urgent'),
            InlineKeyboardButton("📋 View Details", callback_data='admin_tickets')
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=message,
            reply_markup=reply_markup
        )
        return
    
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
    
    # Handle Quick Close button (from dashboard)
    if option.startswith('quick_close_'):
        if user.id != ADMIN_ID:
            await query.answer("❌ Only admin can use this button", show_alert=True)
            return
        
        # Extract user ID from callback data
        target_user_id = int(option.replace('quick_close_', ''))
        
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
        
        await query.answer(f"✅ Closed {ticket['first_name']}'s ticket!", show_alert=True)
        
        # Update the dashboard by editing the message
        # Get updated active tickets
        active_tickets = get_active_tickets()
        
        if not active_tickets:
            await query.edit_message_text(
                text="📭 No open tickets! All clear! ✅"
            )
            return
        
        # Rebuild dashboard
        message = f"🚀 Quick Close Dashboard\n\n"
        message += f"📊 {len(active_tickets)} Open Ticket(s)\n"
        message += f"{'═' * 30}\n\n"
        
        keyboard = []
        
        for ticket in active_tickets[:10]:
            user_id = ticket['user_id']
            first_name = ticket['first_name']
            username = ticket.get('username', 'no_username')
            messages = ticket.get('messages', [])
            msg_count = len(messages)
            
            user_messages = [msg for msg in messages if msg.get('from') == 'user']
            last_msg = user_messages[-1]['text'][:30] + '...' if user_messages and len(user_messages[-1]['text']) > 30 else (user_messages[-1]['text'] if user_messages else "No messages")
            
            message += f"👤 {first_name} (@{username})\n"
            message += f"   💬 {msg_count} msgs | Last: \"{last_msg}\"\n\n"
            
            keyboard.append([
                InlineKeyboardButton(
                    f"✅ Close {first_name}'s Ticket", 
                    callback_data=f'quick_close_{user_id}'
                )
            ])
        
        keyboard.append([
            InlineKeyboardButton("🔄 Refresh", callback_data='admin_quick_close'),
            InlineKeyboardButton("📋 View Details", callback_data='admin_tickets')
        ])
        
        if len(active_tickets) > 10:
            message += f"\n⚠️ Showing first 10 of {len(active_tickets)} tickets"
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await query.edit_message_text(
                text=message,
                reply_markup=reply_markup
            )
        except:
            # If edit fails, send new message
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=message,
                reply_markup=reply_markup
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
        conversation_states[user.id] = {
            'state': 'waiting_wallet_support',
            'option': 'contact_support',
            'data': {}
        }
        
        await query.edit_message_text(
            text='💬 Contact Support\n\n'
                 'We\'re here to help you!\n\n'
                 '📝 Please provide your Solana wallet address connected to the game:'
        )
        return
    
    # Handle Option 1: 5000 Gold for X Post
    if option == 'option_1':
        logger.info(f"User {user.id} selected Option 1")
        conversation_states[user.id] = {
            'state': 'waiting_wallet_option1',
            'option': 'option_1',
            'data': {}
        }
        
        try:
            await query.edit_message_text(
                text='💰 5000 Gold for X Post\n\n'
                     '🎉 Share our game on X (Twitter) and earn 5000 Gold!\n\n'
                     '📝 Please provide your Solana wallet address connected to the game:'
            )
            logger.info(f"Option 1 message sent to user {user.id}")
        except Exception as e:
            logger.error(f"Error in Option 1: {e}")
            await query.answer(f"Error: {e}", show_alert=True)
        return
    
    # Handle Option 2: Promoters Reward
    if option == 'option_2':
        conversation_states[user.id] = {
            'state': 'waiting_wallet_option2',
            'option': 'option_2',
            'data': {}
        }
        
        await query.edit_message_text(
            text='🎁 Promoters Reward\n\n'
                 '💎 Become a promoter and earn exclusive rewards!\n\n'
                 '📝 Please provide your Solana wallet address connected to the game:'
        )
        return
    
    # Handle Option 3: Refer and Earn Reward
    if option == 'option_3':
        conversation_states[user.id] = {
            'state': 'waiting_wallet_option3',
            'option': 'option_3',
            'data': {}
        }
        
        await query.edit_message_text(
            text='👥 Refer and Earn Reward\n\n'
                 '🌟 Invite friends and earn amazing rewards!\n\n'
                 '📝 Please provide your Solana wallet address connected to the game:'
        )
        return
    
    # Handle Option 4: Picaxe Issue
    if option == 'option_4':
        conversation_states[user.id] = {
            'state': 'waiting_wallet_option4',
            'option': 'option_4',
            'data': {}
        }
        
        await query.edit_message_text(
            text='⛏️ Picaxe Issue\n\n'
                 'Having trouble with your Picaxe?\n\n'
                 '📝 Please provide your Solana wallet address connected to the game:'
        )
        return
    
    # Handle Option 5: Wallet Issue
    if option == 'option_5':
        conversation_states[user.id] = {
            'state': 'waiting_wallet_option5',
            'option': 'option_5',
            'data': {}
        }
        
        await query.edit_message_text(
            text='💳 Wallet Issue\n\n'
                 'Having problems with your wallet?\n\n'
                 '📝 Please provide your Solana wallet address:'
        )
        return

# Handle user messages in support chat
async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle messages from users in active support chats or conversation flows."""
    user = update.effective_user
    message_text = update.message.text
    
    # Check if user is in a conversation flow
    if user.id in conversation_states:
        state_data = conversation_states[user.id]
        current_state = state_data['state']
        option = state_data['option']
        
        # Option 1: 5000 Gold for X Post Flow
        if current_state == 'waiting_wallet_option1':
            state_data['data']['wallet'] = message_text
            state_data['state'] = 'waiting_xpost_option1'
            await update.message.reply_text(
                f"✅ Wallet address received: {message_text}\n\n"
                f"📲 Now, please share the link of your X (Twitter) post where you shared our referral link:"
            )
            return
        
        elif current_state == 'waiting_xpost_option1':
            state_data['data']['x_post_link'] = message_text
            wallet = state_data['data']['wallet']
            
            # Create ticket
            save_ticket(user.id, user.username, user.first_name, user.last_name, active=True)
            add_message_to_ticket(user.id, f"💰 5000 Gold for X Post Request", from_user='user')
            add_message_to_ticket(user.id, f"Wallet: {wallet}", from_user='user')
            add_message_to_ticket(user.id, f"X Post Link: {message_text}", from_user='user')
            
            # Notify admin
            await notify_admin(
                context,
                f"🆕 NEW REQUEST: 5000 Gold for X Post\n\n"
                f"👤 {user.first_name} (@{user.username or 'No username'})\n"
                f"🆔 ID: {user.id}\n"
                f"💳 Wallet: {wallet}\n"
                f"🔗 X Post: {message_text}\n\n"
                f"⚡ Review and reply: /reply {user.id} message\n"
                f"🔒 Close when done: /close {user.id}"
            )
            
            await update.message.reply_text(
                "✅ Thank you! Your submission has been received.\n\n"
                "⏳ Please wait while our agent reviews and confirms your post.\n\n"
                "📬 You'll be notified once approved!\n\n"
                "🎫 Your ticket will remain open until the admin closes it."
            )
            
            # Clear conversation state
            del conversation_states[user.id]
            return
        
        # Option 2: Promoters Reward Flow
        elif current_state == 'waiting_wallet_option2':
            state_data['data']['wallet'] = message_text
            state_data['state'] = 'waiting_xpost_option2'
            await update.message.reply_text(
                f"✅ Wallet address received: {message_text}\n\n"
                f"🎉 Thank you for becoming a promoter!\n\n"
                f"📲 Now, please share our post on X (Twitter) and send us the link to your post:"
            )
            return
        
        elif current_state == 'waiting_xpost_option2':
            state_data['data']['x_post_link'] = message_text
            wallet = state_data['data']['wallet']
            
            # Create ticket
            save_ticket(user.id, user.username, user.first_name, user.last_name, active=True)
            add_message_to_ticket(user.id, f"🎁 Promoters Reward Request", from_user='user')
            add_message_to_ticket(user.id, f"Wallet: {wallet}", from_user='user')
            add_message_to_ticket(user.id, f"X Post Link: {message_text}", from_user='user')
            
            # Notify admin
            await notify_admin(
                context,
                f"🆕 NEW REQUEST: Promoters Reward\n\n"
                f"👤 {user.first_name} (@{user.username or 'No username'})\n"
                f"🆔 ID: {user.id}\n"
                f"💳 Wallet: {wallet}\n"
                f"🔗 X Post: {message_text}\n\n"
                f"⚡ Review and reply: /reply {user.id} message\n"
                f"🔒 Close when done: /close {user.id}"
            )
            
            await update.message.reply_text(
                "✅ Thank you!\n\n"
                "⏰ Please wait for 24 hours and your reward will be shared to the wallet address.\n\n"
                "🎫 Your ticket will remain open until the admin closes it."
            )
            
            # Clear conversation state
            del conversation_states[user.id]
            return
        
        # Option 3: Refer and Earn Reward Flow
        elif current_state == 'waiting_wallet_option3':
            state_data['data']['wallet'] = message_text
            state_data['state'] = 'waiting_question_option3'
            await update.message.reply_text(
                f"✅ Wallet address received: {message_text}\n\n"
                f"❓ Are you facing any issue or do you have any questions?"
            )
            return
        
        elif current_state == 'waiting_question_option3':
            wallet = state_data['data']['wallet']
            
            # Create ticket
            save_ticket(user.id, user.username, user.first_name, user.last_name, active=True)
            add_message_to_ticket(user.id, f"👥 Refer and Earn Reward", from_user='user')
            add_message_to_ticket(user.id, f"Wallet: {wallet}", from_user='user')
            add_message_to_ticket(user.id, f"Question/Issue: {message_text}", from_user='user')
            
            # Notify admin
            await notify_admin(
                context,
                f"🆕 NEW REQUEST: Refer and Earn Reward\n\n"
                f"👤 {user.first_name} (@{user.username or 'No username'})\n"
                f"🆔 ID: {user.id}\n"
                f"💳 Wallet: {wallet}\n"
                f"💬 Question: {message_text}\n\n"
                f"⚡ Reply: /reply {user.id} message\n"
                f"🔒 Close: /close {user.id}"
            )
            
            await update.message.reply_text(
                "✅ Thank you for your message!\n\n"
                "🎫 Your ticket will remain open until the admin closes it.\n\n"
                "📬 You'll receive a response soon!"
            )
            
            # Clear conversation state
            del conversation_states[user.id]
            return
        
        # Option 4: Picaxe Issue Flow
        elif current_state == 'waiting_wallet_option4':
            state_data['data']['wallet'] = message_text
            state_data['state'] = 'waiting_issue_option4'
            await update.message.reply_text(
                f"✅ Wallet address received: {message_text}\n\n"
                f"❓ Did you buy any Picaxe or are you facing any issue? Please tell us:"
            )
            return
        
        elif current_state == 'waiting_issue_option4':
            wallet = state_data['data']['wallet']
            
            # Create ticket
            save_ticket(user.id, user.username, user.first_name, user.last_name, active=True)
            add_message_to_ticket(user.id, f"⛏️ Picaxe Issue", from_user='user')
            add_message_to_ticket(user.id, f"Wallet: {wallet}", from_user='user')
            add_message_to_ticket(user.id, f"Issue: {message_text}", from_user='user')
            
            # Notify admin
            await notify_admin(
                context,
                f"🆕 NEW TICKET: Picaxe Issue\n\n"
                f"👤 {user.first_name} (@{user.username or 'No username'})\n"
                f"🆔 ID: {user.id}\n"
                f"💳 Wallet: {wallet}\n"
                f"⛏️ Issue: {message_text}\n\n"
                f"⚡ Reply: /reply {user.id} message\n"
                f"🔒 Close: /close {user.id}"
            )
            
            await update.message.reply_text(
                "✅ Thank you for reporting!\n\n"
                "⏳ Please wait for our support agent.\n\n"
                "⚠️ Due to high requests, it may take some time.\n\n"
                "🎫 Your ticket will remain open until resolved."
            )
            
            # Clear conversation state
            del conversation_states[user.id]
            return
        
        # Option 5: Wallet Issue Flow
        elif current_state == 'waiting_wallet_option5':
            state_data['data']['wallet'] = message_text
            state_data['state'] = 'waiting_issue_option5'
            await update.message.reply_text(
                f"✅ Wallet address received: {message_text}\n\n"
                f"❓ What issue are you facing? Please describe:"
            )
            return
        
        elif current_state == 'waiting_issue_option5':
            wallet = state_data['data']['wallet']
            
            # Create ticket
            save_ticket(user.id, user.username, user.first_name, user.last_name, active=True)
            add_message_to_ticket(user.id, f"💳 Wallet Issue", from_user='user')
            add_message_to_ticket(user.id, f"Wallet: {wallet}", from_user='user')
            add_message_to_ticket(user.id, f"Issue: {message_text}", from_user='user')
            
            # Notify admin
            await notify_admin(
                context,
                f"🆕 NEW TICKET: Wallet Issue\n\n"
                f"👤 {user.first_name} (@{user.username or 'No username'})\n"
                f"🆔 ID: {user.id}\n"
                f"💳 Wallet: {wallet}\n"
                f"🐛 Issue: {message_text}\n\n"
                f"⚡ Reply: /reply {user.id} message\n"
                f"🔒 Close: /close {user.id}"
            )
            
            await update.message.reply_text(
                "✅ Thank you!\n\n"
                "👨‍💼 Our support agent will get back to you soon.\n\n"
                "🎫 Your ticket will remain open until resolved."
            )
            
            # Clear conversation state
            del conversation_states[user.id]
            return
        
        # Contact Support Flow
        elif current_state == 'waiting_wallet_support':
            state_data['data']['wallet'] = message_text
            state_data['state'] = 'waiting_problem_support'
            await update.message.reply_text(
                f"✅ Wallet address received: {message_text}\n\n"
                f"❓ What problem are you facing? Please describe in detail:"
            )
            return
        
        elif current_state == 'waiting_problem_support':
            wallet = state_data['data']['wallet']
            
            # Create ticket
            save_ticket(user.id, user.username, user.first_name, user.last_name, active=True)
            add_message_to_ticket(user.id, f"💬 Contact Support", from_user='user')
            add_message_to_ticket(user.id, f"Wallet: {wallet}", from_user='user')
            add_message_to_ticket(user.id, f"Problem: {message_text}", from_user='user')
            
            # Create inline keyboard with Reply button for admin
            keyboard = [
                [InlineKeyboardButton("💬 Quick Reply", callback_data=f'quick_reply_{user.id}')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Notify admin
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"🆕 NEW SUPPORT TICKET\n\n"
                     f"👤 {user.first_name} (@{user.username or 'No username'})\n"
                     f"🆔 ID: {user.id}\n"
                     f"💳 Wallet: {wallet}\n"
                     f"📝 Problem: {message_text}\n\n"
                     f"⚡ Reply: /reply {user.id} message\n"
                     f"🔒 Close: /close {user.id}",
                reply_markup=reply_markup
            )
            
            await update.message.reply_text(
                "✅ Thank you for contacting us!\n\n"
                "⏳ Please wait for our support agent.\n\n"
                "🎫 Your ticket will remain open until resolved.\n\n"
                "📬 You can continue sending messages and we'll respond!"
            )
            
            # Clear conversation state but keep ticket active
            del conversation_states[user.id]
            return
    
    # Check if user has active support chat (Contact Support option)
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
    
    if not db_pool:
        await update.message.reply_text("❌ Database not connected.")
        return
    
    conn = db_pool.getconn()
    try:
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM tickets")
        total_tickets = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM tickets WHERE active = TRUE")
        active_tickets = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM tickets WHERE active = FALSE")
        closed_tickets = cursor.fetchone()[0]
        
        cursor.close()
        
        message = (
            "📊 Bot Statistics\n\n"
            f"👥 Total Users: {total_users}\n"
            f"🎫 Total Tickets: {total_tickets}\n"
            f"✅ Active Tickets: {active_tickets}\n"
            f"🔒 Closed Tickets: {closed_tickets}\n"
        )
        
        await update.message.reply_text(message)
    finally:
        db_pool.putconn(conn)

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

# Admin command: Search tickets
async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Search for tickets by name, username, or user ID (Admin only)."""
    user = update.effective_user
    
    if user.id != ADMIN_ID:
        await update.message.reply_text("❌ This command is only for admins.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "🔍 Search Tickets\n\n"
            "Usage:\n"
            "/search john - Search by name\n"
            "/search @username - Search by username\n"
            "/search 123456789 - Search by user ID\n\n"
            "Example: /search john"
        )
        return
    
    search_term = ' '.join(context.args).lower().strip()
    
    # Remove @ if searching by username
    if search_term.startswith('@'):
        search_term = search_term[1:]
    
    if not db_pool:
        await update.message.reply_text("❌ Database not connected.")
        return
    
    conn = db_pool.getconn()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Try to search by user ID first (if it's a number)
        if search_term.isdigit():
            cursor.execute('''
                SELECT user_id, username, first_name, last_name, active,
                       created_at, last_updated, messages
                FROM tickets WHERE user_id = %s
            ''', (int(search_term),))
        else:
            # Search by name or username (case-insensitive)
            cursor.execute('''
                SELECT user_id, username, first_name, last_name, active,
                       created_at, last_updated, messages
                FROM tickets 
                WHERE LOWER(first_name) LIKE %s 
                   OR LOWER(last_name) LIKE %s
                   OR LOWER(username) LIKE %s
                ORDER BY last_updated DESC
                LIMIT 20
            ''', (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))
        
        results = cursor.fetchall()
        cursor.close()
        
        if not results:
            await update.message.reply_text(
                f"🔍 No tickets found for: '{search_term}'\n\n"
                f"Try searching by:\n"
                f"- First name\n"
                f"- Username (without @)\n"
                f"- User ID"
            )
            return
        
        message = f"🔍 Search Results for: '{search_term}'\n"
        message += f"Found {len(results)} ticket(s)\n"
        message += f"{'═' * 30}\n\n"
        
        for ticket in results:
            user_id = ticket['user_id']
            first_name = ticket['first_name']
            username = ticket.get('username', 'no_username')
            active = ticket.get('active', False)
            messages = ticket.get('messages', [])
            
            status = "🟢 ACTIVE" if active else "🔴 CLOSED"
            
            message += f"{status}\n"
            message += f"👤 {first_name} (@{username})\n"
            message += f"🆔 ID: {user_id}\n"
            message += f"💬 Messages: {len(messages)}\n"
            
            # Show ticket actions
            if active:
                message += f"⚡ Reply: /reply {user_id} your_message\n"
                message += f"🔒 Close: /close {user_id}\n"
            
            message += f"{'─' * 25}\n\n"
        
        if len(results) == 20:
            message += "⚠️ Showing first 20 results. Be more specific to narrow down."
        
        await update.message.reply_text(message)
    finally:
        db_pool.putconn(conn)

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
    application.add_handler(CommandHandler("search", search_command))
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
    logger.info("   Admin: /search, /tickets, /reply, /close, /stats")
    
    # Set bot commands menu (will be set on first update)
    from telegram import BotCommand, BotCommandScopeChat
    
    async def post_init(application):
        """Set bot commands after initialization."""
        try:
            # Commands for regular users (minimal)
            user_commands = [
                BotCommand("start", "🏠 Start the bot"),
            ]
            
            # Set default commands for all users
            await application.bot.set_my_commands(user_commands)
            logger.info("✅ Default user commands set")
            
            # Admin-only commands (if ADMIN_ID is set)
            if ADMIN_ID:
                admin_commands = [
                    BotCommand("start", "🏠 Open Admin Panel"),
                    BotCommand("search", "🔍 Search tickets (name/username/ID)"),
                    BotCommand("tickets", "🎫 View all active tickets"),
                    BotCommand("stats", "📊 View bot statistics"),
                    BotCommand("reply", "💬 Reply to user (use: /reply ID message)"),
                    BotCommand("close", "🔒 Close ticket (use: /close ID)"),
                    BotCommand("myid", "🆔 Get your Telegram user ID"),
                ]
                
                # Set admin-specific commands
                await application.bot.set_my_commands(
                    admin_commands,
                    scope=BotCommandScopeChat(chat_id=ADMIN_ID)
                )
                logger.info(f"✅ Admin commands set for user {ADMIN_ID}")
        except Exception as e:
            logger.error(f"⚠️ Failed to set commands menu: {e}")
    
    application.post_init = post_init
    
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logger.error(f"❌ Error running bot: {e}")

if __name__ == '__main__':
    main()
