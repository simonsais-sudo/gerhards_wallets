
import logging
from sqlalchemy import select, func, and_
from collections import defaultdict
from src.db.models import Wallet, FundingLink, Transaction
from src.db.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

class StealthDiscovery:
    """
    Finds unlisted lead wallets by analyzing funding networks.
    Target: Addresses that fund multiple influencers but aren't in our list.
    """
    
    async def find_oracle_addresses(self, session, min_wallets=2):
        """
        Identifies 'Oracle' addresses that fund multiple tracked wallets.
        These are often the real 'Smart Money' behind the influencers.
        """
        stmt = (
            select(
                FundingLink.source_address, 
                func.count(func.distinct(FundingLink.dest_wallet_id)).label('dest_count'),
                func.sum(FundingLink.amount).label('total_funded')
            )
            .group_by(FundingLink.source_address)
            .having(func.count(func.distinct(FundingLink.dest_wallet_id)) >= min_wallets)
            .order_by(func.count(func.distinct(FundingLink.dest_wallet_id)).desc())
        )
        
        result = await session.execute(stmt)
        potentials = result.all()
        
        oracles = []
        for addr, count, total in potentials:
            # Check if this address is ALREADY one of our tracked wallets
            track_check = await session.execute(
                select(Wallet).where(Wallet.address == addr)
            )
            if track_check.scalar_one_or_none():
                continue # Already tracked
                
            oracles.append({
                "address": addr,
                "influenced_wallets": count,
                "total_gas_provided": total,
                "type": "ORACLE_FUNDAMENTAL"
            })
            
        return oracles

    async def find_shadow_clusters(self, session, time_window_min=15):
        """
        Finds pairs of wallets that trade identical tokens in tight windows.
        If they do this >3 times, they are likely the same person or a cabal.
        """
        # Get all swaps in the last 7 days
        stmt = (
            select(Transaction.token_address, Transaction.wallet_id, Transaction.timestamp)
            .where(Transaction.tx_type.in_(['BUY', 'SWAP']))
            .where(Transaction.token_address != None)
        )
        
        result = await session.execute(stmt)
        swaps = result.all()
        
        # token -> list of (wallet_id, timestamp)
        token_map = defaultdict(list)
        for addr, wid, ts in swaps:
            token_map[addr].append((wid, ts))
            
        # pairs -> count of shared trades
        pair_counts = defaultdict(int)
        
        for addr, entries in token_map.items():
            for i in range(len(entries)):
                for j in range(i + 1, len(entries)):
                    w1, t1 = entries[i]
                    w2, t2 = entries[j]
                    
                    if w1 == w2: continue
                    
                    # If they traded within time_window_min
                    if abs((t1 - t2).total_seconds()) < (time_window_min * 60):
                        pair = tuple(sorted([w1, w2]))
                        pair_counts[pair] += 1
                        
        shadow_links = []
        for (w1_id, w2_id), count in pair_counts.items():
            if count >= 3: # Must happen at least 3 times
                w1 = await session.get(Wallet, w1_id)
                w2 = await session.get(Wallet, w2_id)
                shadow_links.append({
                    "wallets": [w1.name, w2.name],
                    "shared_trades": count,
                    "type": "SHADOW_LINK"
                })
                
        return shadow_links

def format_stealth_report(oracles, shadow_links):
    report = "🕵️ **STEALTH DISCOVERY REPORT**\n\n"
    
    if oracles:
        report += "🔮 **Potential Oracles Found:**\n"
        report += "_Addresses funding multiple influencers (untracked)_\n"
        for o in oracles[:5]:
            report += f"• `{o['address']}`\n"
            report += f"  ∟ Funds {o['influenced_wallets']} wallets | {o['total_gas_provided']:.1f} SOL\n"
        report += "\n"
        
    if shadow_links:
        report += "🔗 **Shadow Clusters (Hard-Linked):**\n"
        report += "_Wallets trading identical tokens 3+ times simultaneously_\n"
        for s in shadow_links[:5]:
            report += f"• *{s['wallets'][0]}* <--> *{s['wallets'][1]}*\n"
            report += f"  ∟ {s['shared_trades']} Shared Stealth Trades\n"
            
    return report
