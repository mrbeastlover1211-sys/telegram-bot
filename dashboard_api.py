"""
Simple Flask API for Telegram Bot Dashboard
Run this on your Mac to manage tickets through a web interface
"""

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
import os
import json
import asyncio
from telegram import Bot

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})  # Allow browser to connect from anywhere

# Get environment variables
DATABASE_URL = os.environ.get('DATABASE_URL', '')
BOT_TOKEN = os.environ.get('BOT_TOKEN', '')

# Initialize Telegram Bot
telegram_bot = None
if BOT_TOKEN:
    telegram_bot = Bot(token=BOT_TOKEN)
    print(f"✅ Telegram bot initialized")
else:
    print(f"⚠️  BOT_TOKEN not set - messages won't be sent to Telegram")

def get_db_connection():
    """Connect to PostgreSQL database."""
    return psycopg2.connect(DATABASE_URL)

@app.route('/')
def index():
    """Serve the dashboard HTML."""
    try:
        return send_file('dashboard.html')
    except FileNotFoundError:
        return "dashboard.html not found. Make sure you're in the correct directory.", 404

@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({'status': 'ok', 'message': 'API is running'})

@app.route('/api/tickets', methods=['GET'])
def get_tickets():
    """Get all active tickets."""
    category = request.args.get('category', 'all')
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        if category == 'all':
            cursor.execute('''
                SELECT user_id, username, first_name, last_name, 
                       category, messages, created_at, last_updated
                FROM tickets 
                WHERE active = TRUE 
                ORDER BY last_updated DESC
            ''')
        else:
            cursor.execute('''
                SELECT user_id, username, first_name, last_name, 
                       category, messages, created_at, last_updated
                FROM tickets 
                WHERE active = TRUE AND category = %s
                ORDER BY last_updated DESC
            ''', (category,))
        
        tickets = cursor.fetchall()
        cursor.close()
        conn.close()
        
        # Convert to JSON-serializable format
        result = []
        for ticket in tickets:
            result.append({
                'user_id': ticket['user_id'],
                'username': ticket['username'] or 'No username',
                'first_name': ticket['first_name'],
                'last_name': ticket['last_name'] or '',
                'category': ticket['category'],
                'messages': ticket['messages'] or [],
                'created_at': str(ticket['created_at']),
                'last_updated': str(ticket['last_updated'])
            })
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/tickets/<int:user_id>/messages', methods=['GET'])
def get_messages(user_id):
    """Get all messages for a specific ticket."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute('''
            SELECT messages FROM tickets WHERE user_id = %s
        ''', (user_id,))
        
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if result:
            return jsonify(result['messages'] or [])
        else:
            return jsonify([])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/tickets/<int:user_id>/reply', methods=['POST'])
def reply_to_ticket(user_id):
    """Send a reply to a user."""
    try:
        data = request.json
        message = data.get('message', '')
        
        if not message:
            return jsonify({'error': 'Message is required'}), 400
        
        # Add message to database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        from datetime import datetime
        message_obj = json.dumps({
            'text': message,
            'time': datetime.utcnow().strftime('%H:%M:%S'),
            'from': 'admin'
        })
        
        cursor.execute('''
            UPDATE tickets 
            SET messages = messages || %s::jsonb,
                last_updated = CURRENT_TIMESTAMP
            WHERE user_id = %s
        ''', (message_obj, user_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        # Send message via Telegram
        if telegram_bot:
            try:
                # Run async telegram send in sync context
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(
                    telegram_bot.send_message(
                        chat_id=user_id,
                        text=f"💬 Support Team Response:\n\n{message}"
                    )
                )
                loop.close()
                return jsonify({'success': True, 'message': 'Reply sent to user via Telegram!'})
            except Exception as telegram_error:
                return jsonify({'success': True, 'message': f'Saved to database but Telegram error: {str(telegram_error)}'})
        else:
            return jsonify({'success': True, 'message': 'Reply saved (BOT_TOKEN not set, message not sent to Telegram)'})
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/tickets/<int:user_id>/close', methods=['POST'])
def close_ticket(user_id):
    """Close a ticket."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE tickets 
            SET active = FALSE, closed_at = CURRENT_TIMESTAMP
            WHERE user_id = %s
        ''', (user_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        # Notify user via Telegram
        if telegram_bot:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(
                    telegram_bot.send_message(
                        chat_id=user_id,
                        text="✅ Your support ticket has been closed.\n"
                             "Thank you for contacting us!\n\n"
                             "Type /start if you need help again."
                    )
                )
                loop.close()
            except Exception as telegram_error:
                print(f"Failed to notify user via Telegram: {telegram_error}")
        
        return jsonify({'success': True, 'message': 'Ticket closed'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get ticket statistics."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute('''
            SELECT 
                COUNT(*) FILTER (WHERE active = TRUE) as active_tickets,
                COUNT(*) FILTER (WHERE active = FALSE) as closed_tickets,
                COUNT(DISTINCT user_id) as total_users
            FROM tickets
        ''')
        
        stats = cursor.fetchone()
        
        # Get category breakdown
        cursor.execute('''
            SELECT category, COUNT(*) as count 
            FROM tickets 
            WHERE active = TRUE 
            GROUP BY category
        ''')
        
        categories = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return jsonify({
            'active_tickets': stats['active_tickets'],
            'closed_tickets': stats['closed_tickets'],
            'total_users': stats['total_users'],
            'by_category': {cat['category']: cat['count'] for cat in categories}
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("🚀 Starting Dashboard API...")
    print("📊 Dashboard will be available at: http://localhost:5000")
    print("⚠️  Make sure DATABASE_URL environment variable is set!")
    if not BOT_TOKEN:
        print("⚠️  BOT_TOKEN not set - messages won't be sent to Telegram users!")
        print("   Set it with: export BOT_TOKEN='your_bot_token'")
    print()
    app.run(debug=True, port=5000, host='127.0.0.1')
