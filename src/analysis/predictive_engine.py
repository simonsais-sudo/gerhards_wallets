import logging
from datetime import datetime, timedelta
from sqlalchemy import select, update, and_
from src.db.models import Transaction, Wallet, ReloadEvent, WalletStats, FundingLink

logger = logging.getLogger(__name__)

# Thresholds
MIN_RELOAD_SOL = 5.0  # Minimum SOL to consider as "reload"
PREDICTION_WINDOW_MINUTES = 120  # Look for buys within 2 hours of reload


class PredictiveEngine:
    """
    Phase 1: Predictive Engine
    
    Detects wallet "reloads" (incoming funds) and predicts upcoming buys
    based on historical patterns.
    """
    
    async def detect_reload(self, session, wallet, tx, sol_change, source_address=None):
        """
        Called when we detect an incoming SOL transfer.
        Creates a ReloadEvent for tracking.
        """
        if sol_change < MIN_RELOAD_SOL:
            return None
        
        # Check if this reload is already tracked
        existing = await session.execute(
            select(ReloadEvent).where(ReloadEvent.tx_hash == tx.tx_hash)
        )
        if existing.scalar_one_or_none():
            return None
        
        # Create new reload event
        reload = ReloadEvent(
            wallet_id=wallet.id,
            tx_hash=tx.tx_hash,
            amount=sol_change,
            source_address=source_address,
            detected_at=datetime.utcnow()
        )
        session.add(reload)
        await session.flush()
        
        # Get prediction based on history
        prediction = await self.get_reload_prediction(session, wallet.id)
        
        logger.info(f"🔮 RELOAD DETECTED: {wallet.name} received {sol_change:.2f} SOL")
        
        return {
            "reload_id": reload.id,
            "amount": sol_change,
            "prediction": prediction
        }
    
    async def check_reload_resolution(self, session, wallet, new_buy_tx):
        """
        Called when a buy/swap is detected.
        Checks if there's an open reload event to resolve.
        """
        # Find unresolved reloads for this wallet in the last 2 hours
        cutoff = datetime.utcnow() - timedelta(minutes=PREDICTION_WINDOW_MINUTES)
        
        stmt = select(ReloadEvent).where(
            and_(
                ReloadEvent.wallet_id == wallet.id,
                ReloadEvent.followed_by_buy == None,
                ReloadEvent.detected_at >= cutoff
            )
        )
        result = await session.execute(stmt)
        open_reloads = result.scalars().all()
        
        for reload in open_reloads:
            # Calculate time between reload and buy
            time_diff = datetime.utcnow() - reload.detected_at
            minutes = int(time_diff.total_seconds() / 60)
            
            # Mark as resolved
            reload.followed_by_buy = True
            reload.time_to_buy_minutes = minutes
            reload.buy_tx_hash = new_buy_tx.tx_hash
            reload.resolved_at = datetime.utcnow()
            
            logger.info(f"✅ RELOAD RESOLVED: {wallet.name} bought {minutes} min after reload")
            
            # Update wallet stats
            await self.update_prediction_stats(session, wallet.id)
    
    async def resolve_stale_reloads(self, session):
        """
        Called periodically to mark old reloads as 'no buy followed'.
        """
        cutoff = datetime.utcnow() - timedelta(minutes=PREDICTION_WINDOW_MINUTES)
        
        stmt = select(ReloadEvent).where(
            and_(
                ReloadEvent.followed_by_buy == None,
                ReloadEvent.detected_at < cutoff
            )
        )
        result = await session.execute(stmt)
        stale_reloads = result.scalars().all()
        
        for reload in stale_reloads:
            reload.followed_by_buy = False
            reload.resolved_at = datetime.utcnow()
            
        if stale_reloads:
            logger.info(f"📊 Resolved {len(stale_reloads)} stale reloads (no buy)")
    
    async def update_prediction_stats(self, session, wallet_id):
        """
        Recalculate prediction stats for a wallet based on resolved reloads.
        """
        # Get all resolved reloads for this wallet
        stmt = select(ReloadEvent).where(
            and_(
                ReloadEvent.wallet_id == wallet_id,
                ReloadEvent.followed_by_buy != None
            )
        )
        result = await session.execute(stmt)
        reloads = result.scalars().all()
        
        if not reloads:
            return
        
        # Calculate stats
        total = len(reloads)
        buys = sum(1 for r in reloads if r.followed_by_buy)
        buy_times = [r.time_to_buy_minutes for r in reloads if r.followed_by_buy and r.time_to_buy_minutes]
        
        probability = (buys / total) * 100 if total > 0 else 0
        avg_time = sum(buy_times) / len(buy_times) if buy_times else None
        
        # Update or create stats
        stats_stmt = select(WalletStats).where(WalletStats.wallet_id == wallet_id)
        stats_result = await session.execute(stats_stmt)
        stats = stats_result.scalar_one_or_none()
        
        if stats:
            stats.reload_buy_probability = probability
            stats.avg_time_to_buy_after_reload = int(avg_time) if avg_time else None
        
        logger.info(f"📈 Updated prediction: {probability:.0f}% buy after reload, avg {avg_time:.0f} min")
    
    async def get_reload_prediction(self, session, wallet_id):
        """
        Get the current prediction for a wallet.
        """
        stmt = select(WalletStats).where(WalletStats.wallet_id == wallet_id)
        result = await session.execute(stmt)
        stats = result.scalar_one_or_none()
        
        if not stats or stats.reload_buy_probability is None:
            return {
                "probability": None,
                "avg_minutes": None,
                "message": "Not enough data yet - learning..."
            }
        
        return {
            "probability": stats.reload_buy_probability,
            "avg_minutes": stats.avg_time_to_buy_after_reload,
            "message": f"{stats.reload_buy_probability:.0f}% chance of buy within {stats.avg_time_to_buy_after_reload or '?'} min"
        }
    
    async def get_active_predictions(self, session):
        """
        Get all active (unresolved) reload events for display.
        """
        cutoff = datetime.utcnow() - timedelta(minutes=PREDICTION_WINDOW_MINUTES)
        
        stmt = (
            select(ReloadEvent, Wallet.name, WalletStats.reload_buy_probability, WalletStats.avg_time_to_buy_after_reload)
            .join(Wallet, ReloadEvent.wallet_id == Wallet.id)
            .outerjoin(WalletStats, Wallet.id == WalletStats.wallet_id)
            .where(
                and_(
                    ReloadEvent.followed_by_buy == None,
                    ReloadEvent.detected_at >= cutoff
                )
            )
            .order_by(ReloadEvent.detected_at.desc())
        )
        
        result = await session.execute(stmt)
        return result.all()
