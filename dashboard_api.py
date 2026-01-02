"""
Simple FastAPI backend for the dashboard.
Serves real-time data from the database.
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

logger = logging.getLogger(__name__)

app = FastAPI(title="Influencer Tracker API")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Serve the dashboard."""
    return FileResponse("web/dashboard.html")

@app.get("/api/stats")
async def get_stats():
    """Get dashboard statistics."""
    async with AsyncSessionLocal() as session:
        # Total wallets
        wallet_count = await session.execute(select(func.count(Wallet.id)))
        total_wallets = wallet_count.scalar()
        
        # Transactions in last 24h
        yesterday = datetime.now() - timedelta(days=1)
        tx_count = await session.execute(
            select(func.count(Transaction.id)).where(
                Transaction.timestamp >= yesterday
            )
        )
        total_txs = tx_count.scalar()
        
        # Buys in last 24h
        buy_count = await session.execute(
            select(func.count(Transaction.id)).where(
                Transaction.timestamp >= yesterday,
                Transaction.tx_type == 'BUY'
            )
        )
        total_buys = buy_count.scalar()
        
        # Sells in last 24h
        sell_count = await session.execute(
            select(func.count(Transaction.id)).where(
                Transaction.timestamp >= yesterday,
                Transaction.tx_type == 'SELL'
            )
        )
        total_sells = sell_count.scalar()
        
        return {
            "totalWallets": total_wallets,
            "totalTxs": total_txs,
            "totalBuys": total_buys,
            "totalSells": total_sells
        }

@app.get("/api/transactions")
async def get_transactions(limit: int = 50):
    """Get recent transactions."""
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
                "tx_hash": tx.tx_hash[:8] + "..."
            })
        
        return transactions

@app.get("/api/wallets")
async def get_wallets():
    """Get all tracked wallets."""
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
