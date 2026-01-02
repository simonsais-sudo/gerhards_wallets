# 🌐 Remote Access Setup Guide

## Your Server Configuration

**Server IP:** `188.245.162.95`  
**Dashboard Port:** `8888` (configurable)  
**Main Tracker:** Running on PID 1206806  

---

## 🚀 Quick Start - Access the Dashboard

### **Option 1: Direct Access (Simplest)**

Just start the dashboard API and access it from your browser:

```bash
cd /root/gerhard_wallets/influencer_tracker
python3 dashboard_api.py
```

Then open in your browser:
```
http://188.245.162.95:8888
```

---

### **Option 2: Run as Background Service (Recommended)**

This keeps the dashboard running even after you log out:

```bash
# 1. Install the service
sudo cp influencer-tracker-dashboard.service /etc/systemd/system/
sudo systemctl daemon-reload

# 2. Start the service
sudo systemctl start influencer-tracker-dashboard

# 3. Enable auto-start on boot
sudo systemctl enable influencer-tracker-dashboard

# 4. Check status
sudo systemctl status influencer-tracker-dashboard

# 5. View logs
sudo journalctl -u influencer-tracker-dashboard -f
```

Access at: `http://188.245.162.95:8888`

---

### **Option 3: Use Screen/Tmux (Alternative)**

If you don't want to use systemd:

```bash
# Using screen
screen -S dashboard
cd /root/gerhard_wallets/influencer_tracker
python3 dashboard_api.py
# Press Ctrl+A then D to detach

# Reattach later
screen -r dashboard

# OR using tmux
tmux new -s dashboard
cd /root/gerhard_wallets/influencer_tracker
python3 dashboard_api.py
# Press Ctrl+B then D to detach

# Reattach later
tmux attach -t dashboard
```

---

## 🔧 Port Configuration

### **Change the Port:**

Edit the port in the service file or set environment variable:

```bash
# Method 1: Environment variable
export DASHBOARD_PORT=9000
python3 dashboard_api.py

# Method 2: Edit dashboard_api.py
# Change line: PORT = int(os.getenv("DASHBOARD_PORT", "8888"))
# To: PORT = int(os.getenv("DASHBOARD_PORT", "9000"))
```

### **Check Available Ports:**

```bash
# See what ports are in use
sudo netstat -tuln | grep LISTEN

# Check if your port is free
sudo lsof -i :8888
```

---

## 🔒 Firewall Configuration

### **Allow Access Through Firewall:**

```bash
# UFW (Ubuntu Firewall)
sudo ufw allow 8888/tcp
sudo ufw status

# OR iptables
sudo iptables -A INPUT -p tcp --dport 8888 -j ACCEPT
sudo iptables-save
```

### **Cloud Provider Firewall:**

If you're on a cloud provider (AWS, DigitalOcean, etc.), you also need to:

1. **AWS:** Add inbound rule in Security Group for port 8888
2. **DigitalOcean:** Add firewall rule in Cloud Firewalls
3. **Hetzner:** Configure firewall in Cloud Console
4. **Google Cloud:** Add firewall rule in VPC

---

## 🌍 Access URLs

Once running, you can access the dashboard from:

### **Public Access:**
```
http://188.245.162.95:8888
```

### **Local Access (from server):**
```
http://localhost:8888
http://127.0.0.1:8888
```

### **API Endpoints:**
```
http://188.245.162.95:8888/api/stats
http://188.245.162.95:8888/api/transactions
http://188.245.162.95:8888/api/wallets
http://188.245.162.95:8888/health
```

---

## 🔐 Security Recommendations

### **1. Add Basic Authentication (Optional but Recommended)**

Create a simple auth middleware:

```python
# Add to dashboard_api.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets

security = HTTPBasic()

def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(credentials.username, "admin")
    correct_password = secrets.compare_digest(credentials.password, "your_password_here")
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

# Then add to endpoints:
@app.get("/", dependencies=[Depends(verify_credentials)])
async def root():
    return FileResponse("web/dashboard.html")
```

### **2. Use HTTPS with Nginx Reverse Proxy**

```nginx
# /etc/nginx/sites-available/influencer-tracker
server {
    listen 80;
    server_name tracker.yourdomain.com;

    location / {
        proxy_pass http://localhost:8888;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Then get SSL certificate:
```bash
sudo certbot --nginx -d tracker.yourdomain.com
```

### **3. IP Whitelist (Restrict Access)**

```bash
# Only allow your IP
sudo ufw allow from YOUR_IP_ADDRESS to any port 8888

# Or in nginx
location / {
    allow YOUR_IP_ADDRESS;
    deny all;
    proxy_pass http://localhost:8888;
}
```

---

## 🔍 Troubleshooting

### **Dashboard not accessible:**

```bash
# 1. Check if service is running
sudo systemctl status influencer-tracker-dashboard

# 2. Check if port is listening
sudo netstat -tuln | grep 8888

# 3. Check firewall
sudo ufw status
sudo iptables -L -n | grep 8888

# 4. Check logs
sudo journalctl -u influencer-tracker-dashboard -n 50

# 5. Test locally first
curl http://localhost:8888/health
```

### **Port already in use:**

```bash
# Find what's using the port
sudo lsof -i :8888

# Kill the process
sudo kill -9 PID

# Or change the port in dashboard_api.py
```

### **Database connection errors:**

```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Test database connection
PGPASSWORD=tracker_password psql -h localhost -U tracker -d influencer_tracker -c "SELECT 1;"
```

---

## 📊 Service Management Commands

```bash
# Start the dashboard
sudo systemctl start influencer-tracker-dashboard

# Stop the dashboard
sudo systemctl stop influencer-tracker-dashboard

# Restart the dashboard
sudo systemctl restart influencer-tracker-dashboard

# Check status
sudo systemctl status influencer-tracker-dashboard

# View logs (live)
sudo journalctl -u influencer-tracker-dashboard -f

# View last 100 lines
sudo journalctl -u influencer-tracker-dashboard -n 100

# Enable auto-start on boot
sudo systemctl enable influencer-tracker-dashboard

# Disable auto-start
sudo systemctl disable influencer-tracker-dashboard
```

---

## 🎯 Running Multiple Services

Since you have other projects on the server, here's how they coexist:

| Service | Port | Purpose |
|---------|------|---------|
| Main Web Server | 80 | Your other projects |
| Influencer Tracker (Main) | N/A | Background process (PID 1206806) |
| **Dashboard API** | **8888** | **This dashboard** |
| PostgreSQL | 5432 | Database (localhost only) |

All services run independently and won't interfere with each other.

---

## 🚀 Quick Commands Reference

```bash
# Start dashboard (foreground)
python3 dashboard_api.py

# Start dashboard (background with screen)
screen -dmS dashboard python3 dashboard_api.py

# Start dashboard (systemd service)
sudo systemctl start influencer-tracker-dashboard

# Check if running
curl http://localhost:8888/health

# View logs
tail -f /var/log/influencer-tracker-dashboard.log

# Access from browser
# http://188.245.162.95:8888
```

---

## 📱 Mobile Access

The dashboard is responsive and works on mobile devices:

```
http://188.245.162.95:8888
```

Just open this URL on your phone's browser!

---

## 🎨 Custom Domain (Optional)

If you want a custom domain like `tracker.yourdomain.com`:

1. Add A record in DNS: `tracker.yourdomain.com → 188.245.162.95`
2. Set up Nginx reverse proxy (see Security section above)
3. Get SSL certificate with Let's Encrypt
4. Access via `https://tracker.yourdomain.com`

---

## ✅ Verification Checklist

- [ ] Dashboard API is running
- [ ] Port 8888 is open in firewall
- [ ] Can access `http://188.245.162.95:8888` from browser
- [ ] Health check returns OK: `http://188.245.162.95:8888/health`
- [ ] Stats are loading: `http://188.245.162.95:8888/api/stats`
- [ ] Transactions are showing: `http://188.245.162.95:8888/api/transactions`

---

**Need help?** Check the logs:
```bash
sudo journalctl -u influencer-tracker-dashboard -f
```

**Your dashboard is ready at:** `http://188.245.162.95:8888` 🚀
