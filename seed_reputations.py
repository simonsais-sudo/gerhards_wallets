"""
Seed script to populate wallet reputation tiers based on research.
Run this once after updating the database schema.
"""
import asyncio
from sqlalchemy import update
from src.db.database import init_db, AsyncSessionLocal
from src.db.models import Wallet

# Reputation assignments based on research from DEEP_RESEARCH_REPORT.md
REPUTATION_DATA = {
    # TIER A - Verified profitable, trustworthy
    "A": {
        "paulo.sol": "Verified $23M+ profits on WIF, BODEN, BONK. Largest PUPS holder. Confirmed by Lookonchain.",
        "Martini Guy TMG": "Long-term bitcoin analyst since 2016. Less shitcoin gambling, more analytical approach.",
        "Kyle Chasse": "VC investor (Master Ventures, PAID Ignition). No pump & dump accusations found.",
    },
    
    # TIER B - Mixed/unclear reputation
    "B": {
        "Ansem": "170x SOL, 520x WIF verified BUT ZachXBT accused of P&D Oct 2024. Use caution.",
        "Stan Crypto": "Called self 'scammer' (ironically?). Exposes others but unclear motives.",
        "Invest Answers": "Educational focus but promotes some questionable tokens.",
        "Coach K": "High activity but mixed track record.",
        "Dr Profit": "Active trader, some accurate calls but also missed calls.",
    },
    
    # TIER C - Known scammers, use as CONTRARIAN indicators
    "C": {
        "Eunice": "KNOWN SCAMMER - Promoted ThaddeusToken (100% sell-tax honeypot). P&D with Covesting.",
        "Crypto Banter": "ZachXBT documented shill & dump. Lost $134M on Luna while recommending to followers. SatoshiVM scam 2024.",
        "Ran Neuner": "See Crypto Banter - same issues. High risk.",
    },
}


async def seed_reputations():
    """Update wallet reputations in database based on research."""
    await init_db()
    
    async with AsyncSessionLocal() as session:
        updated = 0
        
        for tier, wallets in REPUTATION_DATA.items():
            for name_pattern, notes in wallets.items():
                # Update all wallets matching the name pattern
                stmt = (
                    update(Wallet)
                    .where(Wallet.name.ilike(f"%{name_pattern}%"))
                    .values(reputation_tier=tier, reputation_notes=notes)
                )
                result = await session.execute(stmt)
                count = result.rowcount
                if count > 0:
                    print(f"✅ Updated {count} wallets matching '{name_pattern}' → Tier {tier}")
                    updated += count
        
        await session.commit()
        print(f"\n🎯 Total: {updated} wallets updated with reputation tiers")


if __name__ == "__main__":
    asyncio.run(seed_reputations())
