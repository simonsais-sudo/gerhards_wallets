"""
Contrarian Signal Engine

Generates alerts when:
1. Tier C wallets (known scammers) are buying a token en masse -> WARNING signal
2. Tier A wallets are selling while Tier C is buying -> STRONG CONTRARIAN signal
3. Token was recently promoted on Twitter + influencer buying -> SHILL ALERT
"""
import logging
from datetime import datetime, timedelta
from sqlalchemy import select, and_, func
from src.db.models import Transaction, Wallet, Moment

logger = logging.getLogger(__name__)

# Configuration
CONTRARIAN_WINDOW_MINUTES = 60  # Look for activity in last hour
MIN_TIER_C_BUYERS = 2  # At least 2 Tier C wallets buying = warning


class ContrarianEngine:
    """
    Generates contrarian signals based on wallet reputation tiers.
    
    When scammers buy, it's often a signal to stay away.
    When smart money sells while scammers buy, it's a strong exit signal.
    """
    
    async def analyze_token_activity(self, session, token_symbol: str, token_address: str = None):
        """
        Analyze recent activity on a token by wallet tier.
        Returns contrarian signals if detected.
        """
        if not token_symbol or token_symbol in ['SOL', 'USDC', 'USDT']:
            return None
            
        cutoff = datetime.utcnow() - timedelta(minutes=CONTRARIAN_WINDOW_MINUTES)
        
        # Get all recent buys for this token, grouped by wallet tier
        stmt = (
            select(
                Wallet.reputation_tier,
                Wallet.name,
                Transaction.tx_type,
                Transaction.amount
            )
            .join(Wallet, Transaction.wallet_id == Wallet.id)
            .where(
                and_(
                    Transaction.token_symbol == token_symbol,
                    Transaction.timestamp >= cutoff,
                    Transaction.tx_type.in_(['BUY', 'SWAP', 'SELL'])
                )
            )
        )
        
        result = await session.execute(stmt)
        activity = result.all()
        
        if not activity:
            return None
        
        # Categorize by tier and action
        tier_buys = {'A': [], 'B': [], 'C': [], 'U': []}
        tier_sells = {'A': [], 'B': [], 'C': [], 'U': []}
        
        for tier, name, tx_type, amount in activity:
            tier = tier or 'U'  # Default to unrated
            if tx_type in ('BUY', 'SWAP'):
                tier_buys[tier].append({'name': name, 'amount': amount})
            elif tx_type == 'SELL':
                tier_sells[tier].append({'name': name, 'amount': amount})
        
        signals = []
        
        # SIGNAL 1: Tier C wallets buying en masse
        if len(tier_buys['C']) >= MIN_TIER_C_BUYERS:
            scammer_names = [b['name'][:20] for b in tier_buys['C'][:3]]
            signals.append({
                'type': 'SCAMMER_ACCUMULATION',
                'severity': 'HIGH',
                'token': token_symbol,
                'message': f"⚠️ **CONTRARIAN WARNING**\n"
                          f"Token: ${token_symbol}\n"
                          f"{len(tier_buys['C'])} known scammers buying!\n"
                          f"Wallets: {', '.join(scammer_names)}\n\n"
                          f"_This may be exit liquidity - proceed with caution_"
            })
        
        # SIGNAL 2: Tier A selling while Tier C buying (strongest signal)
        if tier_sells['A'] and tier_buys['C']:
            smart_sellers = [s['name'][:20] for s in tier_sells['A'][:2]]
            scammer_buyers = [b['name'][:20] for b in tier_buys['C'][:2]]
            
            signals.append({
                'type': 'SMART_MONEY_EXIT',
                'severity': 'CRITICAL',
                'token': token_symbol,
                'message': f"🚨 **STRONG EXIT SIGNAL**\n"
                          f"Token: ${token_symbol}\n\n"
                          f"🟢 Smart money SELLING:\n{', '.join(smart_sellers)}\n\n"
                          f"🔴 Scammers BUYING:\n{', '.join(scammer_buyers)}\n\n"
                          f"_Smart money exiting while scammers accumulate = likely dump incoming_"
            })
        
        # SIGNAL 3: Only Tier C activity (no smart money interest)
        if tier_buys['C'] and not tier_buys['A'] and not tier_sells['A']:
            signals.append({
                'type': 'SCAMMER_ONLY',
                'severity': 'MEDIUM',
                'token': token_symbol,
                'message': f"🟡 **LOW QUALITY SIGNAL**\n"
                          f"Token: ${token_symbol}\n"
                          f"Only Tier C wallets active - no smart money interest."
            })
        
        return signals if signals else None
    
    async def check_for_contrarian_on_buy(self, session, wallet, token_symbol, token_address):
        """
        Called when a wallet buys a token.
        Checks if this triggers any contrarian signals.
        """
        signals = await self.analyze_token_activity(session, token_symbol, token_address)
        
        if signals:
            for signal in signals:
                # Save as Moment for history
                moment = Moment(
                    wallet_id=wallet.id,
                    moment_type=f"CONTRARIAN_{signal['type']}",
                    description=signal['message'],
                    severity=10 if signal['severity'] == 'CRITICAL' else 7,
                    detected_at=datetime.utcnow()
                )
                session.add(moment)
                logger.info(f"🔄 Contrarian signal: {signal['type']} on ${token_symbol}")
        
        return signals
    
    async def get_current_warnings(self, session, hours: int = 24):
        """
        Get active contrarian warnings for the dashboard.
        """
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        stmt = (
            select(Moment)
            .where(
                and_(
                    Moment.moment_type.ilike('CONTRARIAN_%'),
                    Moment.detected_at >= cutoff
                )
            )
            .order_by(Moment.detected_at.desc())
            .limit(10)
        )
        
        result = await session.execute(stmt)
        return result.scalars().all()


# Utility function for alerts
def format_contrarian_alert(signal: dict) -> str:
    """Format a contrarian signal for Telegram."""
    return signal['message']
