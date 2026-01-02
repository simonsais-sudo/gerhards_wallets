# 🌐 How to Access Your Dashboard

## 📍 Your Server Details

- **IP Address:** `188.245.162.95`
- **Dashboard Port:** `8888`
- **Access URL:** **http://188.245.162.95:8888**

---

## 🚀 3 Ways to Start the Dashboard

### **Option 1: Quick Start (Easiest)** ⭐

```bash
cd /root/gerhard_wallets/influencer_tracker
./start_dashboard.sh
```

Then open in your browser:
```
http://188.245.162.95:8888
```

---

### **Option 2: As a Service (Runs Forever)**

```bash
# Install and start
sudo cp influencer-tracker-dashboard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl start influencer-tracker-dashboard
sudo systemctl enable influencer-tracker-dashboard

# Check status
sudo systemctl status influencer-tracker-dashboard
```

Access at: `http://188.245.162.95:8888`

---

### **Option 3: Manual Start**

```bash
cd /root/gerhard_wallets/influencer_tracker
python3 dashboard_api.py
```

Access at: `http://188.245.162.95:8888`

---

## 📱 Access from Anywhere

### **From Your Computer:**
1. Open any web browser
2. Go to: `http://188.245.162.95:8888`
3. Done! 🎉

### **From Your Phone:**
1. Open mobile browser
2. Go to: `http://188.245.162.95:8888`
3. Dashboard is mobile-responsive!

---

## 🔍 Verify It's Working

### **Test Endpoints:**

```bash
# Health check
curl http://188.245.162.95:8888/health

# Get stats
curl http://188.245.162.95:8888/api/stats

# Get transactions
curl http://188.245.162.95:8888/api/transactions
```

---

## 🛠️ Troubleshooting

### **Can't access the dashboard?**

1. **Check if it's running:**
   ```bash
   sudo lsof -i :8888
   ```

2. **Check logs:**
   ```bash
   sudo journalctl -u influencer-tracker-dashboard -f
   ```

3. **Restart it:**
   ```bash
   sudo systemctl restart influencer-tracker-dashboard
   ```

4. **Test locally first:**
   ```bash
   curl http://localhost:8888/health
   ```

---

## 📊 What You'll See

The dashboard shows:
- ✅ Total wallets tracked (542)
- ✅ Transactions in last 24h
- ✅ Buys and sells count
- ✅ Live transaction feed with USD values
- ✅ Chain badges (SOL, EVM, BASE)
- ✅ Auto-refresh every 30 seconds

---

## 🎯 Quick Commands

```bash
# Start dashboard
./start_dashboard.sh

# Stop dashboard (if running as service)
sudo systemctl stop influencer-tracker-dashboard

# View logs
sudo journalctl -u influencer-tracker-dashboard -f

# Check status
sudo systemctl status influencer-tracker-dashboard
```

---

## 🔐 Security Note

The dashboard is currently **publicly accessible**. If you want to add password protection, see `REMOTE_ACCESS_GUIDE.md` for security options.

---

## ✅ You're All Set!

**Your dashboard is ready at:**

# 🌐 http://188.245.162.95:8888

Just start it with `./start_dashboard.sh` and open the URL in your browser!

---

**Need more help?** Check `REMOTE_ACCESS_GUIDE.md` for advanced options.
