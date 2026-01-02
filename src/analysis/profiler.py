import logging
import statistics
from sqlalchemy import select
from src.db.models import Transaction, Wallet, WalletStats

logger = logging.getLogger(__name__)

class Profiler:
    """
    Background worker that updates a wallet's statistical profile based on history.
    """
    
    async def update_wallet_stats(self, session, wallet_id):
        try:
            # Fetch last 50 transactions to build a recent profile
            # We focus on Buy/Swap/Transfer sizes
            stmt = select(Transaction).where(
                Transaction.wallet_id == wallet_id
            ).order_by(Transaction.id.desc()).limit(50)
            
            result = await session.execute(stmt)
            txs = result.scalars().all()
            
            if not txs:
                return
            
            # Filter for volume-relevant transactions (amount > 0)
            amounts = []
            for tx in txs:
                if tx.amount and tx.amount > 0:
                    amounts.append(tx.amount)
            
            if not amounts:
                return

            avg_buy = statistics.mean(amounts)
            max_buy = max(amounts)
            tx_count = len(txs) # In this window, or total? Let's just track window for now or fetch count.
            
            # Fetch or Create Stats
            stmt_stats = select(WalletStats).where(WalletStats.wallet_id == wallet_id)
            stats_result = await session.execute(stmt_stats)
            stats = stats_result.scalar_one_or_none()
            
            if not stats:
                stats = WalletStats(wallet_id=wallet_id)
                session.add(stats)
            
            # Update fields
            stats.avg_buy_sol = avg_buy
            stats.max_buy_sol = max_buy
            stats.total_tx_count = tx_count # This is partial, but useful for density
            
            # Note: win_rate requires price history which we don't have yet.
            
            logger.info(f"Updated Profile for Wallet {wallet_id}: Avg={avg_buy:.2f}, Max={max_buy:.2f}")
            
            # Flush to save
            await session.flush()
            
            return stats

        except Exception as e:
            logger.error(f"Profiler Error for Wallet {wallet_id}: {e}")
            return None
