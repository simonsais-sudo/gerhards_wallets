#!/usr/bin/env python3
"""Quick status check for the influencer tracker database."""
import asyncio
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from sqlalchemy import select, func, desc, and_
from src.db.database import AsyncSessionLocal
from src.db.models import Wallet, Transaction, Moment

load_dotenv()

async def main():
    print("=" * 70)
    print("🔍 INFLUENCER TRACKER - QUICK STATUS CHECK")
    print("=" * 70)
    print()
    
    async with AsyncSessionLocal() as session:
        # Count wallets
        wallet_count = await session.execute(select(func.count(Wallet.id)))
        total_wallets = wallet_count.scalar()
        
        # Count by chain
        sol_count = await session.execute(
            select(func.count(Wallet.id)).where(Wallet.chain == 'SOL')
        )
        evm_count = await session.execute(
            select(func.count(Wallet.id)).where(Wallet.chain == 'EVM')
        )
        
        print(f"📊 WALLETS TRACKED:")
        print(f"   Total: {total_wallets}")
        print(f"   Solana: {sol_count.scalar()}")
        print(f"   EVM: {evm_count.scalar()}")
        print()
        
        # Count transactions
        tx_count = await session.execute(select(func.count(Transaction.id)))
        total_txs = tx_count.scalar()
        
        print(f"💰 TRANSACTIONS COLLECTED:")
        print(f"   Total: {total_txs}")
        
        if total_txs > 0:
            # Recent transactions (last 24h)
            yesterday = datetime.now() - timedelta(days=1)
            recent_tx = await session.execute(
                select(func.count(Transaction.id)).where(
                    Transaction.timestamp >= yesterday
                )
            )
            recent_count = recent_tx.scalar()
            print(f"   Last 24h: {recent_count}")
            
            # Get most recent transaction
            latest_tx = await session.execute(
                select(Transaction, Wallet)
                .join(Wallet, Transaction.wallet_id == Wallet.id)
                .order_by(desc(Transaction.timestamp))
                .limit(1)
            )
            latest = latest_tx.first()
            
            if latest:
                tx, wallet = latest
                print(f"\n   Latest Transaction:")
                print(f"   └─ Wallet: {wallet.name}")
                print(f"   └─ Time: {tx.timestamp}")
                print(f"   └─ Type: {tx.tx_type}")
                print(f"   └─ Hash: {tx.tx_hash[:16]}...")
        print()
        
        # Count moments (high-value events)
        moment_count = await session.execute(select(func.count(Moment.id)))
        total_moments = moment_count.scalar()
        
        print(f"🎯 ALPHA MOMENTS DETECTED:")
        print(f"   Total: {total_moments}")
        
        if total_moments > 0:
            # Recent moments
            yesterday = datetime.now() - timedelta(days=1)
            recent_moments = await session.execute(
                select(func.count(Moment.id)).where(
                    Moment.timestamp >= yesterday
                )
            )
            print(f"   Last 24h: {recent_moments.scalar()}")
            
            # Top moments
            top_moments = await session.execute(
                select(Moment, Wallet)
                .join(Wallet, Moment.wallet_id == Wallet.id)
                .order_by(desc(Moment.timestamp))
                .limit(5)
            )
            
            print(f"\n   🔥 Recent Alpha Moments:")
            for moment, wallet in top_moments:
                print(f"   └─ {wallet.name}: {moment.token_symbol or 'Unknown'} - {moment.moment_type}")
                print(f"      {moment.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        
        print()
        print("=" * 70)
        print(f"✅ System Status: {'RUNNING' if total_txs > 0 else 'INITIALIZING'}")
        print(f"⏰ Checked at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)

if __name__ == "__main__":
    asyncio.run(main())
