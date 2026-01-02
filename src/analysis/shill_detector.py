import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, and_, desc, func
from src.db.models import Transaction, Wallet, WalletStats

logger = logging.getLogger(__name__)

class ShillDetector:
    """
    Phase 5: Narrative Intelligence (Manual Mode)
    
    Allows checking a token to see if tracked influencers 
    bought it BEFORE the current hype/shill.
    """
    
    async def check_token_history(self, session, token_input):
        """
        Check who bought this token and when.
        token_input can be symbol ($WIF) or address.
        """
        # Clean input
        token_clean = token_input.upper().replace("$", "").strip()
        
        # Search by Symbol OR Address
        stmt = (
            select(Transaction, Wallet.name)
            .join(Wallet, Transaction.wallet_id == Wallet.id)
            .where(
                and_(
                    Transaction.tx_type == 'SWAP',
                    Transaction.amount > 0, # Buys only
                    (func.upper(Transaction.token_symbol) == token_clean) | 
                    (Transaction.token_address == token_clean)
                )
            )
            .order_by(desc(Transaction.timestamp))
            .limit(20)
        )
        
        result = await session.execute(stmt)
        txs = result.all()
        
        if not txs:
            return None
            
        # Analyze the history
        analysis = {
            "token": token_clean,
            "total_buys": len(txs),
            "earliest_buy": None,
            "buyers": [],
            "volume_detected": 0.0
        }
        
        earliest_time = datetime.now(timezone.utc)
        
        for tx, wallet_name in txs:
            # Handle timezone
            tx_time = tx.timestamp
            if tx_time.tzinfo is None:
                tx_time = tx_time.replace(tzinfo=timezone.utc)
                
            if tx_time < earliest_time:
                earliest_time = tx_time
                
            analysis["buyers"].append({
                "wallet": wallet_name,
                "amount": tx.amount,
                "time": tx_time,
                "hash": tx.tx_hash
            })
            
            if tx.amount:
                analysis["volume_detected"] += tx.amount
                
        analysis["earliest_buy"] = earliest_time
        
        return analysis

    def get_shill_verdict(self, analysis):
        """
        Determine if it looks like a pre-shill accumulation.
        """
        now = datetime.now(timezone.utc)
        earliest = analysis["earliest_buy"]
        
        # Time delta
        diff = now - earliest
        days = diff.days
        hours = diff.seconds // 3600
        
        impact = "UNKNOWN"
        if analysis["total_buys"] >= 3:
            impact = "HIGH"
        elif analysis["total_buys"] >= 1:
            impact = "MEDIUM"
            
        return {
            "days_ago": days,
            "hours_ago": hours,
            "impact": impact,
            "buyer_count": len(set(b["wallet"] for b in analysis["buyers"]))
        }
