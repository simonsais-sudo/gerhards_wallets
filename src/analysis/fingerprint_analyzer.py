import logging
from datetime import datetime, timedelta
from sqlalchemy import select, and_, func
from src.db.models import Transaction, WalletStats
import aiohttp

logger = logging.getLogger(__name__)

# Style thresholds
SNIPER_HOLD_HOURS = 24  # Sells within 24h = Sniper
HOLDER_HOLD_HOURS = 168  # Holds >7 days = Holder


class FingerprintAnalyzer:
    """
    Phase 3: Strategy Fingerprint
    
    Analyzes each influencer's trading DNA:
    - Win Rate: % of profitable trades
    - Hold Time: Average time between buy and sell
    - Exit Pattern: DUMP (instant), LADDER (gradual), HOLD
    - Trading Style: SNIPER, TRADER, HOLDER
    """
    
    def __init__(self):
        self.price_cache = {}  # token -> price (USD)
    
    async def get_token_price(self, token_address):
        """
        Get current token price from Jupiter API.
        """
        if not token_address:
            return None
            
        if token_address in self.price_cache:
            return self.price_cache[token_address]
        
        try:
            url = f"https://api.jup.ag/price/v2?ids={token_address}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=5) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("data") and token_address in data["data"]:
                            price = float(data["data"][token_address].get("price", 0))
                            self.price_cache[token_address] = price
                            return price
        except Exception as e:
            logger.debug(f"Price fetch failed for {token_address}: {e}")
        
        return None
    
    async def analyze_trade_outcome(self, session, wallet_id, buy_tx):
        """
        Check if a buy trade was profitable by finding the sell.
        Returns: (is_win, hold_time_hours, pnl_percent)
        """
        if not buy_tx.token_address or not buy_tx.timestamp:
            return None, None, None
        
        # Look for a sell of the same token after this buy
        stmt = select(Transaction).where(
            and_(
                Transaction.wallet_id == wallet_id,
                Transaction.token_address == buy_tx.token_address,
                Transaction.tx_type == 'SWAP',
                Transaction.timestamp > buy_tx.timestamp,
                Transaction.amount < 0  # Negative = sold
            )
        ).order_by(Transaction.timestamp.asc()).limit(1)
        
        result = await session.execute(stmt)
        sell_tx = result.scalar_one_or_none()
        
        if not sell_tx:
            # Still holding - check current price
            current_price = await self.get_token_price(buy_tx.token_address)
            if current_price and buy_tx.amount_usd:
                # Compare current value to entry
                # This is approximation - we don't track exact token amounts
                return None, None, None
            return None, None, None
        
        # Calculate hold time
        hold_time = sell_tx.timestamp - buy_tx.timestamp
        hold_hours = hold_time.total_seconds() / 3600
        
        # Calculate PnL if we have USD values
        if buy_tx.amount_usd and sell_tx.amount_usd:
            pnl_percent = ((abs(sell_tx.amount_usd) - buy_tx.amount_usd) / buy_tx.amount_usd) * 100
            is_win = pnl_percent > 0
        else:
            # Simple heuristic: if they sold, assume even
            is_win = None
            pnl_percent = None
        
        return is_win, hold_hours, pnl_percent
    
    async def calculate_fingerprint(self, session, wallet_id):
        """
        Calculate full trading fingerprint for a wallet.
        """
        # Get all buy transactions
        stmt = select(Transaction).where(
            and_(
                Transaction.wallet_id == wallet_id,
                Transaction.tx_type == 'SWAP',
                Transaction.amount > 0  # Positive = buy
            )
        ).order_by(Transaction.timestamp.desc()).limit(50)
        
        result = await session.execute(stmt)
        buys = result.scalars().all()
        
        if not buys:
            return None
        
        wins = 0
        losses = 0
        hold_times = []
        pnls = []
        
        for buy in buys:
            is_win, hold_hours, pnl = await self.analyze_trade_outcome(session, wallet_id, buy)
            
            if is_win is not None:
                if is_win:
                    wins += 1
                else:
                    losses += 1
            
            if hold_hours is not None:
                hold_times.append(hold_hours)
            
            if pnl is not None:
                pnls.append(pnl)
        
        # Calculate stats
        total_resolved = wins + losses
        win_rate = (wins / total_resolved * 100) if total_resolved > 0 else None
        avg_hold = sum(hold_times) / len(hold_times) if hold_times else None
        avg_pnl = sum(pnls) / len(pnls) if pnls else None
        
        # Determine trading style
        style = self._classify_style(avg_hold)
        
        # Update WalletStats
        stats_stmt = select(WalletStats).where(WalletStats.wallet_id == wallet_id)
        stats_result = await session.execute(stats_stmt)
        stats = stats_result.scalar_one_or_none()
        
        if stats:
            stats.win_rate = win_rate
            stats.avg_hold_time_hours = avg_hold
            stats.preferred_sector = style  # Reusing field for style
            stats.trades_analyzed = len(buys)
            
            logger.info(f"📊 Fingerprint: WinRate={win_rate:.0f}%, Hold={avg_hold:.1f}h, Style={style}")
        
        return {
            "win_rate": win_rate,
            "avg_hold_hours": avg_hold,
            "style": style,
            "trades_analyzed": len(buys),
            "avg_pnl": avg_pnl
        }
    
    def _classify_style(self, avg_hold_hours):
        """Classify trading style based on hold time."""
        if avg_hold_hours is None:
            return "UNKNOWN"
        
        if avg_hold_hours < SNIPER_HOLD_HOURS:
            return "SNIPER"  # Quick flips
        elif avg_hold_hours < HOLDER_HOLD_HOURS:
            return "TRADER"  # Medium term
        else:
            return "HOLDER"  # Long term conviction
    
    async def get_profile(self, session, wallet_id):
        """Get cached profile or calculate fresh."""
        stats_stmt = select(WalletStats).where(WalletStats.wallet_id == wallet_id)
        result = await session.execute(stats_stmt)
        stats = result.scalar_one_or_none()
        
        if stats and stats.win_rate is not None:
            return {
                "win_rate": stats.win_rate,
                "avg_hold_hours": stats.avg_hold_time_hours,
                "style": stats.preferred_sector or "UNKNOWN",
                "trades_analyzed": stats.trades_analyzed or 0,
                "alpha_score": stats.alpha_score or 100
            }
        
        # Calculate fresh if no data
        return await self.calculate_fingerprint(session, wallet_id)
