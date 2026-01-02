
import asyncio
from src.db.database import AsyncSessionLocal
from src.db.models import Wallet
from sqlalchemy import update

async def bootstrap_reputations():
    tiers = {
        "A": ["paulo.sol", "Kyle Chasse", "Martini Guy", "Paulo"],
        "B": ["Ansem", "Crypto Banter", "Ran Neuner", "Eunice Wong", "Coach K", "Dr Profit", "Invest Answers", "Fefe", "Kyle Doops", "Dr Profit"],
        "C": ["SajadAli", "Crypto Gains"] 
    }
    
    async with AsyncSessionLocal() as session:
        for tier, names in tiers.items():
            for name in names:
                # Use LIKE to match names like "paulo.sol 1", "paulo.sol 2", etc.
                stmt = (
                    update(Wallet)
                    .where(Wallet.name.like(f"%{name}%"))
                    .values(reputation_tier=tier)
                )
                await session.execute(stmt)
        
        await session.commit()
    print("✅ Reputations bootstrapped. Lead-Follower engine is now calibrated.")

if __name__ == "__main__":
    asyncio.run(bootstrap_reputations())
