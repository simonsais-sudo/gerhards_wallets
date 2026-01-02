#!/bin/bash
# Quick start script for the Influencer Tracker Dashboard

set -e

echo "🚀 Starting Influencer Tracker Dashboard..."
echo ""

# Get server IP
SERVER_IP=$(hostname -I | awk '{print $1}')
PORT=8888

# Check if port is in use
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "⚠️  Port $PORT is already in use!"
    echo "   Checking what's running..."
    sudo lsof -i :$PORT
    echo ""
    read -p "Kill the process and continue? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        PID=$(lsof -ti:$PORT)
        sudo kill -9 $PID
        echo "✅ Process killed"
    else
        echo "❌ Aborted"
        exit 1
    fi
fi

# Check if database is running
if ! systemctl is-active --quiet postgresql; then
    echo "⚠️  PostgreSQL is not running. Starting it..."
    sudo systemctl start postgresql
    sleep 2
fi

# Check database connection
if PGPASSWORD=tracker_password psql -h localhost -U tracker -d influencer_tracker -c "SELECT 1;" >/dev/null 2>&1; then
    echo "✅ Database connection OK"
else
    echo "❌ Database connection failed!"
    echo "   Run: ./setup_database.sh"
    exit 1
fi

echo ""
echo "=" * 70
echo "🌐 Dashboard will be accessible at:"
echo ""
echo "   Public:  http://$SERVER_IP:$PORT"
echo "   Local:   http://localhost:$PORT"
echo ""
echo "   API:     http://$SERVER_IP:$PORT/api/stats"
echo "   Health:  http://$SERVER_IP:$PORT/health"
echo ""
echo "=" * 70
echo ""
echo "📝 Press Ctrl+C to stop the dashboard"
echo ""

# Start the dashboard
cd "$(dirname "$0")"
python3 dashboard_api.py
