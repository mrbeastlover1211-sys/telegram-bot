# 🤖 Bot Start/Stop Control

Easy way to start and stop your Telegram bot to save money!

---

## 🎯 Quick Guide:

### **Stop Bot (Save Money):**
When you're not using it, stop the bot to save ~$0.46/month

**In Railway Dashboard:**
1. Go to Railway.app
2. Click your bot service
3. Click the three dots (...)
4. Click "Stop"

### **Start Bot (When Needed):**
When you want to accept user messages again

**In Railway Dashboard:**
1. Go to Railway.app
2. Click your bot service
3. Click the three dots (...)
4. Click "Restart" or "Redeploy"

---

## 💡 When to Run the Bot:

### **Keep Bot RUNNING when:**
- ✅ You're actively managing tickets
- ✅ Users need to contact you
- ✅ You want 24/7 support availability
- 💰 Cost: ~$0.46/month

### **STOP Bot when:**
- ✅ You're not managing tickets
- ✅ Off-hours / weekends
- ✅ Want to save money
- 💰 Cost: $0

---

## 🔄 Typical Usage Pattern:

### **Option 1: Business Hours Only**
```
Monday 9 AM:  Start bot
Monday 6 PM:  Stop bot
Tuesday 9 AM: Start bot
Tuesday 6 PM: Stop bot
...

Estimated cost: ~$0.15/month (instead of $0.46)
```

### **Option 2: Weekdays Only**
```
Monday 9 AM:  Start bot
Friday 6 PM:  Stop bot
(Off all weekend)

Estimated cost: ~$0.30/month
```

### **Option 3: Always On**
```
Never stop it

Cost: ~$0.46/month
Convenience: Maximum
```

---

## ⚡ Quick Start/Stop:

### **Using Railway Dashboard (Easiest):**

**Stop:**
1. Railway.app → Your project
2. Click bot service
3. Three dots (...) → "Stop"

**Start:**
1. Railway.app → Your project
2. Click bot service
3. Three dots (...) → "Restart"

### **Using Railway CLI (Advanced):**

**Install Railway CLI:**
```bash
brew install railway
railway login
railway link
```

**Stop Bot:**
```bash
railway down
```

**Start Bot:**
```bash
railway up -d
```

---

## 📊 Cost Comparison:

| Usage Pattern | Hours/Month | Cost/Month | Savings |
|---------------|-------------|------------|---------|
| **24/7 Always On** | 720 hours | ~$0.46 | $0 |
| **Weekdays 9-6** | ~200 hours | ~$0.15 | $0.31 |
| **Weekdays 9-9** | ~260 hours | ~$0.20 | $0.26 |
| **When Dashboard Open** | ~40 hours | ~$0.03 | $0.43 |
| **Off** | 0 hours | $0.00 | $0.46 |

---

## 🎯 My Recommendation:

### **If Budget is Tight:**
- Stop bot when not needed
- Start it when you're managing tickets
- Save ~$0.30-0.40/month

### **If You Want Convenience:**
- Keep it running 24/7
- Only ~$0.46/month (1.5 cents/day)
- Users can always contact you

---

## ⚠️ Important Notes:

1. **When bot is STOPPED:**
   - Users can't message it
   - No new tickets created
   - Existing tickets in database are safe

2. **When bot STARTS again:**
   - Takes ~30 seconds to start
   - All old tickets are still there
   - Users can message again

3. **The Dashboard:**
   - Works even if bot is stopped (can view old tickets)
   - Can't send messages to users if bot is stopped
   - Always free (runs on your Mac)

---

## 🚀 Best Practices:

1. **Start bot before managing tickets**
2. **Stop bot at end of day if saving money**
3. **Always restart if users complain**
4. **Keep database (PostgreSQL) running always** (it's free)

---

Happy bot managing! 🎉
