import logging
from datetime import datetime, timedelta
from sqlalchemy import select, and_, func
from collections import defaultdict
from src.db.models import Transaction, Wallet, FundingLink, Moment

logger = logging.getLogger(__name__)

# Thresholds
CABAL_TIME_WINDOW_MINUTES = 30  # Wallets buying same token within 30 min = suspicious
MIN_CLUSTER_SIZE = 2  # At least 2 wallets to form a cluster


class CabalDetector:
    """
    Phase 2: Cabal Detection
    
    Detects coordinated wallet activity:
    1. Track funding sources for each wallet
    2. When multiple wallets buy the same token in a short window → CABAL ALERT
    3. Calculate "cluster confidence" based on shared funding + timing
    """
    
    async def track_funding(self, session, wallet, source_address, amount, tx_hash):
        """
        Called when we detect an incoming transfer.
        Records the funding link for graph building.
        """
        if not source_address or amount < 0.1:
            return
        
        # Check if link already exists
        existing = await session.execute(
            select(FundingLink).where(FundingLink.tx_hash == tx_hash)
        )
        if existing.scalar_one_or_none():
            return
        
        link = FundingLink(
            source_address=source_address,
            dest_wallet_id=wallet.id,
            amount=amount,
            tx_hash=tx_hash
        )
        session.add(link)
        
        logger.info(f"📎 Funding tracked: {source_address[:8]}... → {wallet.name}")
    
    async def detect_cluster_buy(self, session, wallet, token_symbol, token_address):
        """
        Called after a swap is detected.
        Checks if other tracked wallets bought the same token recently.
        """
        if not token_symbol or token_symbol in ['SOL', 'USDC', 'USDT']:
            return None  # Skip stablecoins
        
        cutoff = datetime.utcnow() - timedelta(minutes=CABAL_TIME_WINDOW_MINUTES)
        
        # Find other wallets that bought this token recently
        stmt = (
            select(Transaction, Wallet.name, Wallet.id)
            .join(Wallet, Transaction.wallet_id == Wallet.id)
            .where(
                and_(
                    Transaction.tx_type.in_(['BUY', 'SWAP']),  # Support both types
                    Transaction.token_symbol == token_symbol,
                    Transaction.timestamp >= cutoff,
                    Transaction.wallet_id != wallet.id
                )
            )
            .order_by(Transaction.timestamp.desc())
        )
        
        result = await session.execute(stmt)
        other_buyers = result.all()
        
        if len(other_buyers) >= MIN_CLUSTER_SIZE - 1:  # -1 because current wallet counts
            # CABAL DETECTED!
            buyer_names = [wallet.name] + [b[1] for b in other_buyers[:5]]
            cluster_size = len(other_buyers) + 1
            
            # Check if they share funding sources (increases confidence)
            confidence = await self._calculate_cluster_confidence(
                session, wallet.id, [b[2] for b in other_buyers]
            )
            
            alert = (
                f"🕸️ **CABAL ALERT**\n"
                f"Token: ${token_symbol}\n"
                f"Cluster: {cluster_size} wallets\n"
                f"Buyers: {', '.join(buyer_names[:4])}\n"
                f"Confidence: {confidence:.0f}%"
            )
            
            # Save as Moment
            moment = Moment(
                wallet_id=wallet.id,
                moment_type="CABAL",
                description=alert,
                severity=10,  # Maximum severity
                detected_at=datetime.utcnow()
            )
            session.add(moment)
            
            logger.info(f"🕸️ CABAL DETECTED: {cluster_size} wallets on ${token_symbol}")
            
            return {
                "token": token_symbol,
                "cluster_size": cluster_size,
                "wallets": buyer_names,
                "confidence": confidence,
                "alert": alert
            }
        
        return None
    
    async def _calculate_cluster_confidence(self, session, wallet_id, other_wallet_ids):
        """
        Calculate confidence score based on shared funding sources.
        More shared sources = higher confidence of coordination.
        """
        if not other_wallet_ids:
            return 50.0  # Base confidence just from timing
        
        # Get funding sources for current wallet
        stmt1 = select(FundingLink.source_address).where(
            FundingLink.dest_wallet_id == wallet_id
        )
        result1 = await session.execute(stmt1)
        my_sources = set(r[0] for r in result1.all())
        
        if not my_sources:
            return 50.0
        
        # Check overlap with other wallets
        shared_count = 0
        for other_id in other_wallet_ids:
            stmt2 = select(FundingLink.source_address).where(
                FundingLink.dest_wallet_id == other_id
            )
            result2 = await session.execute(stmt2)
            other_sources = set(r[0] for r in result2.all())
            
            if my_sources & other_sources:  # Any overlap
                shared_count += 1
        
        # Base 50% for timing, +10% per shared funding source (max 100%)
        confidence = min(100.0, 50.0 + (shared_count * 15))
        
        return confidence
    
    async def get_active_cabals(self, session, hours=24):
        """
        Get recent cabal detections for display.
        """
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        stmt = (
            select(Moment, Wallet.name)
            .join(Wallet, Moment.wallet_id == Wallet.id)
            .where(
                and_(
                    Moment.moment_type == "CABAL",
                    Moment.detected_at >= cutoff
                )
            )
            .order_by(Moment.detected_at.desc())
            .limit(10)
        )
        
        result = await session.execute(stmt)
        return result.all()
