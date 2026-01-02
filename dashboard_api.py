"""
Dashboard API with configurable port and host.
Run this separately from other projects on the server.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy import select, func, desc
from datetime import datetime, timedelta
from src.db.database import AsyncSessionLocal
from src.db.models import Wallet, Transaction
import logging
import os

logger = logging.getLogger(__name__)

# Configuration
PORT = int(os.getenv("DASHBOARD_PORT", "8888"))  # Use port 8888 by default
HOST = os.getenv("DASHBOARD_HOST", "0.0.0.0")  # Listen on all interfaces

app = FastAPI(
    title="Influencer Tracker API",
    description="Real-time on-chain alpha intelligence",
    version="1.0.0"
)

# Enable CORS for remote access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Serve the dashboard."""
    return FileResponse("web/dashboard.html")

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "influencer-tracker-dashboard"
    }

@app.get("/api/stats")
async def get_stats():
    """Get dashboard statistics."""
    try:
        async with AsyncSessionLocal() as session:
            # Total wallets
            wallet_count = await session.execute(select(func.count(Wallet.id)))
            total_wallets = wallet_count.scalar() or 0
            
            # Transactions in last 24h
            yesterday = datetime.now() - timedelta(days=1)
            tx_count = await session.execute(
                select(func.count(Transaction.id)).where(
                    Transaction.timestamp >= yesterday
                )
            )
            total_txs = tx_count.scalar() or 0
            
            # Buys in last 24h
            buy_count = await session.execute(
                select(func.count(Transaction.id)).where(
                    Transaction.timestamp >= yesterday,
                    Transaction.tx_type == 'BUY'
                )
            )
            total_buys = buy_count.scalar() or 0
            
            # Sells in last 24h
            sell_count = await session.execute(
                select(func.count(Transaction.id)).where(
                    Transaction.timestamp >= yesterday,
                    Transaction.tx_type == 'SELL'
                )
            )
            total_sells = sell_count.scalar() or 0
            
            return {
                "totalWallets": total_wallets,
                "totalTxs": total_txs,
                "totalBuys": total_buys,
                "totalSells": total_sells
            }
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        return {
            "totalWallets": 0,
            "totalTxs": 0,
            "totalBuys": 0,
            "totalSells": 0,
            "error": str(e)
        }

@app.get("/api/transactions")
async def get_transactions(limit: int = 50):
    """Get recent transactions."""
    try:
        async with AsyncSessionLocal() as session:
            stmt = (
                select(Transaction, Wallet)
                .join(Wallet, Transaction.wallet_id == Wallet.id)
                .order_by(desc(Transaction.timestamp))
                .limit(limit)
            )
            result = await session.execute(stmt)
            rows = result.all()
            
            transactions = []
            for tx, wallet in rows:
                transactions.append({
                    "id": tx.id,
                    "wallet": wallet.name,
                    "type": tx.tx_type,
                    "token": tx.token_symbol or "UNKNOWN",
                    "amount": tx.amount or 0,
                    "usd_value": tx.amount_usd,
                    "chain": tx.chain,
                    "timestamp": tx.timestamp.isoformat(),
                    "tx_hash": tx.tx_hash[:8] + "..." if tx.tx_hash else "N/A"
                })
            
            return transactions
    except Exception as e:
        logger.error(f"Error fetching transactions: {e}")
        return []

@app.get("/api/wallets")
async def get_wallets():
    """Get all tracked wallets."""
    try:
        async with AsyncSessionLocal() as session:
            stmt = select(Wallet).where(Wallet.is_active == True)
            result = await session.execute(stmt)
            wallets = result.scalars().all()
            
            return [
                {
                    "id": w.id,
                    "name": w.name,
                    "address": w.address,
                    "chain": w.chain,
                    "confidence_score": w.confidence_score,
                    "reputation_tier": w.reputation_tier
                }
                for w in wallets
            ]
    except Exception as e:
        logger.error(f"Error fetching wallets: {e}")
        return []

if __name__ == "__main__":
    import uvicorn
    
    print("=" * 70)
    print("🚀 Starting Influencer Tracker Dashboard API")
    print("=" * 70)
    print(f"📡 Host: {HOST}")
    print(f"🔌 Port: {PORT}")
    print(f"🌐 Access URL: http://188.245.162.95:{PORT}")
    print(f"🏠 Local URL: http://localhost:{PORT}")
    print("=" * 70)
    print()
    
    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
        log_level="info"
    )
