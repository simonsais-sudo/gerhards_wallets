
import asyncio
from src.db.database import AsyncSessionLocal
from src.db.models import Transaction, Wallet
from sqlalchemy import select, func

async def check_db():
    async with AsyncSessionLocal() as session:
        count = await session.execute(select(func.count(Transaction.id)))
        tx_count = count.scalar()
        print(f"Total Transactions in DB: {tx_count}")
        
        # Get latest scans
        latest = await session.execute(select(Transaction).order_by(Transaction.timestamp.desc()).limit(5))
        for tx in latest.scalars():
            print(f"[{tx.timestamp}] {tx.tx_hash[:10]}... {tx.tx_type} {tx.token_symbol}")

if __name__ == "__main__":
    asyncio.run(check_db())
