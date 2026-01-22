# 📊 Local Dashboard Setup Guide

Run this dashboard on your Mac to manage Telegram bot tickets through a beautiful web interface!

---

## 🚀 Quick Start (3 Easy Steps)

### Step 1: Install Dependencies

Open Terminal on your Mac and run:

```bash
# Install Flask and required packages
pip3 install flask flask-cors psycopg2-binary
```

### Step 2: Set Database URL

You need to set the `DATABASE_URL` environment variable. Get this from Railway:

1. Go to Railway → Your project → PostgreSQL service
2. Click "Variables" tab
3. Copy the `DATABASE_URL` value

Then in Terminal, run:

```bash
# Replace with your actual DATABASE_URL from Railway
export DATABASE_URL="postgresql://postgres:password@containers-us-west-123.railway.app:5432/railway"
```

**Note:** You'll need to do this every time you open a new Terminal window, OR add it to your `.zshrc` file:

```bash
echo 'export DATABASE_URL="your_database_url_here"' >> ~/.zshrc
source ~/.zshrc
```

### Step 3: Start the Dashboard

```bash
# Make sure you're in the project folder
cd /path/to/telegram-bot

# Start the API server
python3 dashboard_api.py
```

You should see:
```
🚀 Starting Dashboard API...
📊 Dashboard will be available at: http://localhost:5000
⚠️  Make sure DATABASE_URL environment variable is set!

 * Running on http://127.0.0.1:5000
```

### Step 4: Open Dashboard

Open your browser (Safari or Chrome) and go to:

```
http://localhost:5000
```

**That's it!** 🎉 You should see the dashboard!

---

## 🎯 How to Use the Dashboard

### Main Features:

1. **View All Tickets**
   - See all open tickets in card format
   - Shows user info, category, wallet, last message

2. **Filter by Category**
   - Click any category button at the top
   - 💰 5000 Gold, 🎁 Promoters, 👥 Refer & Earn, etc.

3. **Chat with Users**
   - Click **💬 Chat** button on any ticket
   - See full conversation history
   - Type and send replies instantly
   - User receives your message in Telegram!

4. **Close Tickets**
   - Click **🔒 Close** button
   - Confirms before closing
   - User gets notified in Telegram

5. **Auto-Refresh**
   - Dashboard refreshes every 30 seconds automatically
   - Or click **🔄 Refresh** button manually

---

## 📱 Dashboard Layout

```
┌──────────────────────────────────────────┐
│  🎮 Gold Mining Bot Dashboard            │
│                                           │
│  Stats: 15 Active | 42 Closed | 57 Users │
└──────────────────────────────────────────┘

┌──────────────────────────────────────────┐
│ Filters:                                  │
│ [All] [💰 5000 Gold] [🎁 Promoters]...   │
│                           [🔄 Refresh]    │
└──────────────────────────────────────────┘

┌──────────────────────────────────────────┐
│ 📋 John Doe                               │
│ @johndoe • ID: 123456789                  │
│ 💰 5000 Gold for X Post                   │
│                                            │
│ 💳 Wallet: ABC123xyz...                   │
│ 💬 Last: "Here is my X post link..."      │
│ 📊 Total Messages: 5                       │
│                                            │
│ [💬 Chat]  [🔒 Close]                     │
└──────────────────────────────────────────┘
```

---

## 🔧 Troubleshooting

### Problem: "Failed to load tickets"

**Solution:**
1. Make sure `dashboard_api.py` is running
2. Check if `DATABASE_URL` is set correctly:
   ```bash
   echo $DATABASE_URL
   ```
3. Try restarting the API server

### Problem: "Connection refused"

**Solution:**
- Make sure the API is running on port 5000
- Check if another app is using port 5000
- Try accessing: http://127.0.0.1:5000 instead

### Problem: Messages not sending to Telegram

**Solution:**
Currently, the dashboard only stores messages in the database. To send messages to Telegram users, you need to integrate with the bot. This requires the bot to be running and checking for new admin messages.

---

## 🎨 Features You Get

| Feature | Status |
|---------|--------|
| ✅ View all tickets | Working |
| ✅ Filter by category | Working |
| ✅ See ticket details | Working |
| ✅ Chat interface | Working |
| ✅ Close tickets | Working |
| ✅ Auto-refresh | Working |
| ✅ Real-time stats | Working |
| ⚠️ Send to Telegram | Requires bot integration |

---

## 💡 Tips

1. **Keep Terminal Open:** Don't close the Terminal window where the API is running
2. **Bookmark the URL:** Add http://localhost:5000 to your bookmarks
3. **Multiple Tabs:** You can open the dashboard in multiple browser tabs
4. **Mobile Access:** Access from your phone using your Mac's IP address (on same WiFi)

---

## 🔒 Security Notes

- This runs **locally on your Mac only**
- No one else can access it (unless on same network)
- Database credentials are in environment variables (secure)
- Always use `localhost`, not your public IP

---

## 📝 Next Steps (Optional)

### Make it Start Automatically:

Create a simple startup script:

```bash
# Create startup script
nano ~/start-dashboard.sh
```

Add this content:
```bash
#!/bin/bash
export DATABASE_URL="your_database_url_here"
cd /path/to/telegram-bot
python3 dashboard_api.py
```

Save and make executable:
```bash
chmod +x ~/start-dashboard.sh
```

Now just run:
```bash
~/start-dashboard.sh
```

---

## 🆘 Need Help?

If something doesn't work:

1. Check Terminal for error messages
2. Make sure DATABASE_URL is set
3. Verify Railway PostgreSQL is accessible
4. Try restarting the API server

---

## 🎉 Enjoy Your Dashboard!

You now have a beautiful web interface to manage your Telegram bot tickets!

- No need to type commands
- See everything at a glance
- Chat with users easily
- Close tickets with one click

Happy managing! 🚀
