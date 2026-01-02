"""
AI Play Finder - Proactively identifies trading opportunities.
Runs after every scan and pushes plays to the user.
"""
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Transaction, Wallet, WalletStats, Moment, ReloadEvent

logger = logging.getLogger(__name__)


class PlayFinder:
    """
    Analyzes recent activity to find actionable plays.
    Criteria for a "play":
    1. CLUSTER BUY: 2+ high-conviction wallets bought same token in last 30 min
    2. SMART MONEY ENTRY: Top win-rate wallet enters new position
    3. RELOAD + BUY: Wallet received funds AND immediately bought (active trader)
    4. ACCUMULATION SPIKE: Single wallet making multiple buys of same token
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.min_wallets_for_cluster = 2
        self.lookback_minutes = 30
        
    async def find_plays(self) -> list[dict]:
        """Main entry point. Returns list of play opportunities."""
        plays = []
        
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=self.lookback_minutes)
        
        # 1. Check for Cluster Buys (multiple wallets, same token)
        cluster_plays = await self._find_cluster_buys(cutoff)
        plays.extend(cluster_plays)
        
        # 2. Check for Smart Money Entries (high win-rate wallets)
        smart_plays = await self._find_smart_money_entries(cutoff)
        plays.extend(smart_plays)
        
        # 3. Check for Reload-to-Buy patterns
        reload_plays = await self._find_reload_buys(cutoff)
        plays.extend(reload_plays)
        
        return plays
    
    async def _find_cluster_buys(self, cutoff: datetime) -> list[dict]:
        """Find tokens bought by 2+ wallets recently."""
        plays = []
        
        # Group recent buys by token
        stmt = (
            select(
                Transaction.token_symbol,
                Transaction.token_address,
                func.count(func.distinct(Transaction.wallet_id)).label('wallet_count'),
                func.sum(Transaction.amount).label('total_amount')
            )
            .where(Transaction.timestamp >= cutoff)
            .where(Transaction.tx_type == 'SWAP')
            .where(Transaction.token_symbol.isnot(None))
            .where(Transaction.token_symbol != 'SOL')
            .where(Transaction.token_symbol != 'USDC')
            .where(Transaction.token_symbol != 'USDT')
            .group_by(Transaction.token_symbol, Transaction.token_address)
            .having(func.count(func.distinct(Transaction.wallet_id)) >= self.min_wallets_for_cluster)
            .order_by(desc('wallet_count'))
            .limit(3)
        )
        
        result = await self.session.execute(stmt)
        clusters = result.all()
        
        for symbol, address, wallet_count, total_amount in clusters:
            # Get wallet names for this cluster
            wallet_stmt = (
                select(Wallet.name)
                .join(Transaction, Transaction.wallet_id == Wallet.id)
                .where(Transaction.token_symbol == symbol)
                .where(Transaction.timestamp >= cutoff)
                .distinct()
                .limit(5)
            )
            wallet_result = await self.session.execute(wallet_stmt)
            wallet_names = [w[0] for w in wallet_result.all()]
            
            plays.append({
                "type": "CLUSTER_BUY",
                "token": symbol,
                "address": address,
                "wallet_count": wallet_count,
                "wallets": wallet_names,
                "confidence": min(95, 50 + (wallet_count * 15)),
                "reason": f"{wallet_count} influencers buying simultaneously"
            })
        
        return plays
    
    async def _find_smart_money_entries(self, cutoff: datetime) -> list[dict]:
        """Find new entries from wallets with >60% win rate."""
        plays = []
        
        # Get recent buys from high win-rate wallets
        stmt = (
            select(
                Wallet.name,
                Transaction.token_symbol,
                Transaction.amount,
                WalletStats.win_rate,
                WalletStats.alpha_score
            )
            .join(Wallet, Transaction.wallet_id == Wallet.id)
            .join(WalletStats, Wallet.id == WalletStats.wallet_id)
            .where(Transaction.timestamp >= cutoff)
            .where(Transaction.tx_type == 'SWAP')
            .where(WalletStats.win_rate >= 0.6)  # 60%+ win rate
            .where(WalletStats.trades_analyzed >= 3)  # At least 3 closed trades
            .where(Transaction.token_symbol.isnot(None))
            .where(Transaction.token_symbol.notin_(['SOL', 'USDC', 'USDT', 'ETH']))
            .order_by(desc(WalletStats.win_rate))
            .limit(3)
        )
        
        result = await self.session.execute(stmt)
        entries = result.all()
        
        for wallet_name, token, amount, win_rate, alpha in entries:
            plays.append({
                "type": "SMART_MONEY",
                "token": token,
                "wallet": wallet_name,
                "amount": amount,
                "win_rate": win_rate,
                "alpha": alpha,
                "confidence": int(win_rate * 100),
                "reason": f"Proven trader ({win_rate*100:.0f}% win rate) entered"
            })
        
        return plays
    
    async def _find_reload_buys(self, cutoff: datetime) -> list[dict]:
        """Find wallets that reloaded AND bought within 30 min."""
        plays = []
        
        # Get recent reloads that were followed by buys
        stmt = (
            select(
                Wallet.name,
                ReloadEvent.sol_amount,
                Transaction.token_symbol,
                Transaction.amount
            )
            .join(Wallet, ReloadEvent.wallet_id == Wallet.id)
            .join(
                Transaction,
                (Transaction.wallet_id == ReloadEvent.wallet_id) &
                (Transaction.timestamp >= ReloadEvent.detected_at) &
                (Transaction.timestamp <= ReloadEvent.detected_at + timedelta(minutes=30))
            )
            .where(ReloadEvent.detected_at >= cutoff)
            .where(Transaction.tx_type == 'SWAP')
            .where(Transaction.token_symbol.isnot(None))
            .where(Transaction.token_symbol.notin_(['SOL', 'USDC', 'USDT']))
            .limit(3)
        )
        
        result = await self.session.execute(stmt)
        reloads = result.all()
        
        for wallet_name, reload_amount, token, buy_amount in reloads:
            plays.append({
                "type": "RELOAD_BUY",
                "token": token,
                "wallet": wallet_name,
                "reload_amount": reload_amount,
                "buy_amount": buy_amount,
                "confidence": 70,
                "reason": f"Loaded {reload_amount:.1f} SOL → Immediately bought"
            })
        
        return plays


def format_play_alert(play: dict) -> str:
    """Format a play into a Telegram message."""
    
    if play["type"] == "CLUSTER_BUY":
        wallets_str = ", ".join(play["wallets"][:3])
        if len(play["wallets"]) > 3:
            wallets_str += f" +{len(play['wallets'])-3} more"
        
        return (
            f"🎯 *CLUSTER ALERT: ${play['token']}*\n\n"
            f"👥 *{play['wallet_count']} influencers* buying now\n"
            f"📋 {wallets_str}\n\n"
            f"🔥 Confidence: {play['confidence']}%\n"
            f"_{play['reason']}_"
        )
    
    elif play["type"] == "SMART_MONEY":
        return (
            f"🧠 *SMART MONEY: ${play['token']}*\n\n"
            f"👤 *{play['wallet']}* entered\n"
            f"📊 Win Rate: {play['win_rate']*100:.0f}%\n"
            f"💰 Size: {play['amount']:.2f}\n\n"
            f"🔥 Confidence: {play['confidence']}%\n"
            f"_{play['reason']}_"
        )
    
    elif play["type"] == "RELOAD_BUY":
        return (
            f"⚡ *ACTIVE TRADER: ${play['token']}*\n\n"
            f"👤 *{play['wallet']}*\n"
            f"💵 Loaded: {play['reload_amount']:.1f} SOL\n"
            f"🛒 Bought: {play['buy_amount']:.2f}\n\n"
            f"🔥 Confidence: {play['confidence']}%\n"
            f"_{play['reason']}_"
        )
    
    return f"📢 New Play: {play}"
