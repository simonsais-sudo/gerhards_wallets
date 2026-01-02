import logging
from sqlalchemy import select
from src.db.models import Transaction, Wallet, Moment, WalletStats
from src.analysis.profiler import Profiler
from datetime import datetime

logger = logging.getLogger(__name__)

class PatternEngine:
    """
    Analyzes sequences of transactions for a single wallet to predict future moves.
    Uses learned profiles for dynamic thresholds.
    """
    
    def __init__(self):
        self.profiler = Profiler()

    async def analyze_behavior(self, session, wallet, current_tx):
        """
        Check for specific behavioral patterns based on the new transaction 
        and the wallet's historical profile.
        """
        try:
            # First, update the wallet's profile with the new transaction
            stats = await self.profiler.update_wallet_stats(session, wallet.id)
            
            # 1. ANOMALY DETECTION (Dynamic Threshold)
            if current_tx.amount and current_tx.amount > 0:
                if stats and stats.avg_buy_sol and stats.avg_buy_sol > 0:
                    # Calculate deviation from their normal behavior
                    deviation = current_tx.amount / stats.avg_buy_sol
                    
                    if deviation >= 3.0:
                        # This is 3x their normal size - very unusual
                        pct = (deviation - 1) * 100
                        return await self._register_moment(
                            session, wallet, current_tx,
                            "WHALE_MOVE",
                            f"🐋 **Whale Move Detected**\n"
                            f"Size: {current_tx.amount:.2f} {current_tx.token_symbol or 'units'}\n"
                            f"Deviation: **+{pct:.0f}%** from their avg ({stats.avg_buy_sol:.2f})",
                            severity=9
                        )
                    elif deviation >= 2.0:
                        pct = (deviation - 1) * 100
                        return await self._register_moment(
                            session, wallet, current_tx,
                            "ABOVE_AVG",
                            f"📈 **Above Average Activity**\n"
                            f"Size: {current_tx.amount:.2f} (+{pct:.0f}% vs avg {stats.avg_buy_sol:.2f})",
                            severity=6
                        )
                else:
                    # No stats yet - building profile, skip anomaly check
                    pass

            # 2. ACCUMULATION Pattern (repeated buys of same token)
            if current_tx.tx_type == 'SWAP' and current_tx.token_symbol:
                history = await self._get_recent_txs(session, wallet.id, limit=5)
                
                match_count = 1
                for tx in history:
                    if tx.id == current_tx.id:
                        continue
                    if tx.tx_type == 'SWAP' and tx.token_symbol == current_tx.token_symbol:
                        match_count += 1
                
                if match_count >= 3:
                    return await self._register_moment(
                        session, wallet, current_tx,
                        "ACCUMULATION",
                        f"🔄 **Accumulation Alert**\n"
                        f"{match_count} buys of ${current_tx.token_symbol} recently. Building position.",
                        severity=8
                    )

            # 3. NEW TOKEN (buying something they've never bought before)
            if current_tx.tx_type == 'SWAP' and current_tx.token_address:
                # Check if this token appears in their history
                stmt = select(Transaction).where(
                    Transaction.wallet_id == wallet.id,
                    Transaction.token_address == current_tx.token_address,
                    Transaction.id != current_tx.id
                ).limit(1)
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()
                
                if not existing:
                    return await self._register_moment(
                        session, wallet, current_tx,
                        "NEW_TOKEN",
                        f"🆕 **New Token Alert**\n"
                        f"First time buying ${current_tx.token_symbol or 'Unknown'}. Fresh entry.",
                        severity=7
                    )
            
            return None

        except Exception as e:
            logger.error(f"Pattern Analysis Error: {e}")
            return None

    async def _get_recent_txs(self, session, wallet_id, limit=10):
        stmt = select(Transaction).where(
            Transaction.wallet_id == wallet_id
        ).order_by(Transaction.id.desc()).limit(limit)
        result = await session.execute(stmt)
        return result.scalars().all()

    async def _register_moment(self, session, wallet, tx, m_type, desc, severity):
        """Create a Moment entry and return the description for alerting."""
        moment = Moment(
            wallet_id=wallet.id,
            tx_hash=tx.tx_hash,
            moment_type=m_type,
            description=desc,
            severity=severity,
            detected_at=datetime.utcnow()
        )
        session.add(moment)
        return desc
