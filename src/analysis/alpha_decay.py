import logging
from datetime import datetime, timedelta
from sqlalchemy import select, and_, func
from src.db.models import Transaction, Wallet, WalletStats

logger = logging.getLogger(__name__)

# Thresholds
COPY_WINDOW_SECONDS = 300  # 5 minutes - if someone buys same token within 5 min = copier
ALPHA_DECAY_PER_COPIER = 5  # Lose 5% alpha per copier


class AlphaDecayTracker:
    """
    Phase 4: Alpha Decay Tracker
    
    Measures how "crowded" an influencer's alpha is:
    - When influencer buys, check how many wallets copy within 5 min
    - More copiers = faster price impact = less profit for followers
    - Calculate "Alpha Score" that decays with copiers
    """
    
    async def track_copiers_for_trade(self, session, wallet, token_symbol, token_address, buy_timestamp):
        """
        Called after an influencer buys.
        Waits and checks how many other wallets bought the same token.
        
        Note: This should be called AFTER a delay (e.g., via background task)
        """
        if not token_symbol or token_symbol in ['SOL', 'USDC', 'USDT']:
            return 0
        
        cutoff_start = buy_timestamp
        cutoff_end = buy_timestamp + timedelta(seconds=COPY_WINDOW_SECONDS)
        
        # Count other wallets that bought same token in the window
        stmt = (
            select(func.count(Transaction.id.distinct()))
            .where(
                and_(
                    Transaction.tx_type == 'SWAP',
                    Transaction.token_symbol == token_symbol,
                    Transaction.timestamp >= cutoff_start,
                    Transaction.timestamp <= cutoff_end,
                    Transaction.wallet_id != wallet.id,
                    Transaction.amount > 0  # Buys only
                )
            )
        )
        
        result = await session.execute(stmt)
        copier_count = result.scalar() or 0
        
        if copier_count > 0:
            logger.info(f"📉 Alpha tracked: {copier_count} copiers on ${token_symbol} after {wallet.name}")
        
        return copier_count
    
    async def update_alpha_score(self, session, wallet_id, new_copier_count):
        """
        Update the wallet's alpha score based on copier counts.
        Uses exponential moving average.
        """
        stats_stmt = select(WalletStats).where(WalletStats.wallet_id == wallet_id)
        result = await session.execute(stats_stmt)
        stats = result.scalar_one_or_none()
        
        if not stats:
            return
        
        # Update average copiers (EMA with 0.3 weight for new data)
        old_avg = stats.avg_copiers_per_trade or 0
        new_avg = (0.3 * new_copier_count) + (0.7 * old_avg)
        stats.avg_copiers_per_trade = new_avg
        
        # Calculate alpha score (100 = perfect, 0 = totally crowded)
        # Each copier reduces by ALPHA_DECAY_PER_COPIER
        alpha = max(0, 100 - (new_avg * ALPHA_DECAY_PER_COPIER))
        stats.alpha_score = alpha
        
        logger.info(f"📊 Alpha updated: {wallet_id} → Score {alpha:.0f} (Avg {new_avg:.1f} copiers)")
        
        return alpha
    
    async def get_alpha_leaderboard(self, session, limit=10):
        """
        Get wallets ranked by alpha score (highest = least crowded).
        """
        stmt = (
            select(Wallet.name, WalletStats.alpha_score, WalletStats.avg_copiers_per_trade, WalletStats.win_rate)
            .join(WalletStats, Wallet.id == WalletStats.wallet_id)
            .where(WalletStats.alpha_score.isnot(None))
            .order_by(WalletStats.alpha_score.desc())
            .limit(limit)
        )
        
        result = await session.execute(stmt)
        return result.all()
    
    async def get_crowded_wallets(self, session, limit=10):
        """
        Get wallets with lowest alpha (most crowded/copied).
        """
        stmt = (
            select(Wallet.name, WalletStats.alpha_score, WalletStats.avg_copiers_per_trade)
            .join(WalletStats, Wallet.id == WalletStats.wallet_id)
            .where(WalletStats.alpha_score.isnot(None))
            .where(WalletStats.alpha_score < 70)  # Below 70 = crowded
            .order_by(WalletStats.alpha_score.asc())
            .limit(limit)
        )
        
        result = await session.execute(stmt)
        return result.all()
    
    async def quick_copier_check(self, session, token_symbol, exclude_wallet_id, minutes=30):
        """
        Quick check: How many tracked wallets bought this token recently?
        Used to give real-time "crowded" warning.
        """
        if not token_symbol or token_symbol in ['SOL', 'USDC', 'USDT']:
            return 0
        
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        
        stmt = (
            select(func.count(Transaction.wallet_id.distinct()))
            .where(
                and_(
                    Transaction.tx_type == 'SWAP',
                    Transaction.token_symbol == token_symbol,
                    Transaction.timestamp >= cutoff,
                    Transaction.wallet_id != exclude_wallet_id
                )
            )
        )
        
        result = await session.execute(stmt)
        return result.scalar() or 0
