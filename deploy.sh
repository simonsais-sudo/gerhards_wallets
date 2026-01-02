#!/bin/bash
# Deployment script for influencer tracker with transaction filtering

set -e  # Exit on error

echo "===================================="
echo "Influencer Tracker Deployment"
echo "===================================="

# Server details
SERVER="root@188.245.162.95"
REMOTE_PATH="/root/gerhard_wallets/influencer_tracker"
LOCAL_PATH="/Volumes/SD/Mac/gerhard_wallets/influencer_tracker"

echo -e "\n📦 Step 1: Syncing code to server..."
rsync -avz --delete \
    --exclude '.git' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude 'postgres_data' \
    --exclude '.env' \
    --exclude 'venv/' \
    --exclude 'config/bot_config.json' \
    "$LOCAL_PATH/" "$SERVER:$REMOTE_PATH/"

echo -e "\n🔧 Step 2: Rebuilding Docker container..."
ssh "$SERVER" "cd $REMOTE_PATH && docker compose down"
ssh "$SERVER" "cd $REMOTE_PATH && docker compose build --no-cache"

echo -e "\n🚀 Step 3: Starting services..."
ssh "$SERVER" "cd $REMOTE_PATH && docker compose up -d"

echo -e "\n⏳ Step 4: Waiting for services to stabilize (10 seconds)..."
sleep 10

echo -e "\n📊 Step 5: Checking status..."
ssh "$SERVER" "cd $REMOTE_PATH && docker compose ps"

echo -e "\n📜 Step 6: Showing recent logs..."
ssh "$SERVER" "cd $REMOTE_PATH && docker compose logs --tail=50 bot"

echo -e "\n✅ Deployment complete!"
echo -e "\n📌 Monitoring commands:"
echo "   • Live logs: ssh $SERVER \"cd $REMOTE_PATH && docker compose logs -f bot\""
echo "   • Restart: ssh $SERVER \"cd $REMOTE_PATH && docker compose restart bot\""
echo "   • Stop: ssh $SERVER \"cd $REMOTE_PATH && docker compose down\""
