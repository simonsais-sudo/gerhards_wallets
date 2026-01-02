
import logging
from sqlalchemy import select, and_, func
from datetime import datetime, timedelta
from src.db.models import Wallet, Transaction, Moment
from src.db.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

class LeadFollowerEngine:
    """
    Analyzes the 'Time-to-Shill' (TTS).
    Identifies tokens bought by Tier A (Whales) that haven't been bought 
    by Tier B (Influencers) yet.
    """
    
    def __init__(self, session=None):
        self._session = session
        # Wallets that usually move FIRST
        self.LEAD_TIERS = ['A'] # Paulo.sol, top whales
        # Wallets that usually move SECOND (bringing volume)
        self.FOLLOWER_TIERS = ['B'] # Top influencers, shillers

    async def analyze_token_lag(self, session, token_address):
        """
        Calculates the historical lag between Tier A and Tier B entries 
        for a specific token.
        """
        if not token_address: return None
        
        # Get all buys for this token
        stmt = (
            select(Transaction, Wallet.reputation_tier, Wallet.name)
            .join(Wallet, Transaction.wallet_id == Wallet.id)
            .where(
                and_(
                    Transaction.token_address == token_address,
                    Transaction.tx_type.in_(['BUY', 'SWAP'])
                )
            )
            .order_by(Transaction.timestamp.asc())
        )
        
        result = await session.execute(stmt)
        buys = result.all()
        
        if not buys: return None
        
        leads = [b for b in buys if b[1] in self.LEAD_TIERS]
        followers = [b for b in buys if b[1] in self.FOLLOWER_TIERS]
        
        if not leads or not followers:
            return {
                "token": token_address,
                "status": "INCOMPLETE_DATA",
                "lead_count": len(leads),
                "follower_count": len(followers)
            }
            
        first_lead_time = leads[0][0].timestamp
        first_follower_time = followers[0][0].timestamp
        
        lag_seconds = (first_follower_time - first_lead_time).total_seconds()
        
        return {
            "token": token_address,
            "status": "COMPLETE",
            "lag_minutes": lag_seconds / 60,
            "lead_wallet": leads[0][2],
            "first_shiller": followers[0][2]
        }

    async def find_active_alpha_gaps(self, session):
        """
        Finds tokens currently held by Tier A that Tier B hasn't started pumping yet.
        This IS the profit window.
        """
        # 1. Get tokens bought by Tier A in last 24h
        cutoff = datetime.utcnow() - timedelta(hours=24)
        
        lead_tx_stmt = (
            select(Transaction.token_address, Transaction.token_symbol, Wallet.name, Transaction.timestamp)
            .join(Wallet, Transaction.wallet_id == Wallet.id)
            .where(
                and_(
                    Wallet.reputation_tier == 'A',
                    Transaction.tx_type.in_(['BUY', 'SWAP']),
                    Transaction.timestamp >= cutoff,
                    Transaction.token_address != None
                )
            )
        )
        
        lead_buys = (await session.execute(lead_tx_stmt)).all()
        
        gaps = []
        for lead_buy in lead_buys:
            token_addr = lead_buy[0]
            symbol = lead_buy[1]
            lead_name = lead_buy[2]
            lead_time = lead_buy[3]
            
            # 2. Check if ANY Tier B has bought it yet
            follower_check_stmt = (
                select(func.count(Transaction.id))
                .join(Wallet, Transaction.wallet_id == Wallet.id)
                .where(
                    and_(
                        Wallet.reputation_tier == 'B',
                        Transaction.token_address == token_addr
                    )
                )
            )
            
            follower_count = (await session.execute(follower_check_stmt)).scalar()
            
            if follower_count == 0:
                # ALPHA GAP DETECTED!
                # Tier A is in, Tier B is NOT.
                gaps.append({
                    "symbol": symbol,
                    "address": token_addr,
                    "lead_wallet": lead_name,
                    "lead_time": lead_time,
                    "opportunity": "FREE_ALPHA"
                })
                
        return gaps

def format_gap_alert(gap):
    """Formats an alert for the Telegram bot."""
    return (
        f"⚡ **ALPHA GAP DETECTED**\n"
        f"Token: `${gap['symbol']}`\n"
        f"Lead Wallet: `{gap['lead_wallet']}`\n"
        f"Entry Time: {gap['lead_time'].strftime('%H:%M UTC')}\n"
        f"Status: 🟢 Tier B Followers NOT yet in.\n\n"
        f"🎯 **STRATEGY:** High conviction frontrun. Tier A entry detected without shill volume yet."
    )
