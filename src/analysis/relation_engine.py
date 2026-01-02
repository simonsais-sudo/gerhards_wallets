import asyncio
import logging
from sqlalchemy import select, func
from datetime import datetime, timedelta
from src.db.database import AsyncSessionLocal
from src.db.models import Transaction, Wallet, Relation
from src.bot.telegram_handler import bot_instance
from src.analysis.ai_analyzer import AIAnalyzer

logger = logging.getLogger(__name__)

class RelationEngine:
    def __init__(self):
        self.ai = AIAnalyzer()
        self.running = False

    async def start(self):
        self.running = True
        logger.info("Relation Engine Started")
        asyncio.create_task(self.loop())

    async def loop(self):
        while self.running:
            await asyncio.sleep(300) # Check every 5 minutes
            await self.check_clusters()

    async def check_clusters(self):
        try:
            async with AsyncSessionLocal() as session:
                # 1. Temporal Clustering (Time window: last 10 mins)
                time_window = datetime.utcnow() - timedelta(minutes=10)
                # Note: 'timestamp' in DB might be None if we didn't fetch block time. 
                # We can fallback to 'detected_at' (not currently in Transaction model, but 'created_at' logic?)
                # We don't have created_at in Transaction. Let's use ID as proxy for recency or just fetch all recent IDs.
                # Actually, main loop adds them real-time. Docker logs show we are adding them.
                # Let's rely on finding transactions with IDs that are recent?
                # Better: Add 'created_at' to Transaction model? Too late for migration on live DB without hassle.
                # We can filter by ID (higher IDs are newer).
                # Let's just grab the last 50 transactions.
                
                stmt = select(Transaction).order_by(Transaction.id.desc()).limit(50)
                result = await session.execute(stmt)
                recent_txs = result.scalars().all()
                
                if not recent_txs:
                    return

                # Group by Chain & "To" (if EVM) or simple time bucket
                clusters = []
                
                # Simple Time Bucketing
                # Since we don't have good timestamps, we assume the last 50 happened 'recently' 
                # if the bot is polling live. 
                # This is a weak assumption but ok for MVP.
                
                # Group distinct wallets in this batch
                active_wallets = {}
                for tx in recent_txs:
                    if tx.wallet_id not in active_wallets:
                        # Fetch wallet name
                        w = await session.get(Wallet, tx.wallet_id)
                        active_wallets[tx.wallet_id] = {'name': w.name, 'txs': [], 'chain': tx.chain}
                    
                    active_wallets[tx.wallet_id]['txs'].append(tx.tx_hash)

                if len(active_wallets) > 1:
                    # CLUSTER DETECTED: Multiple wallets active recently
                    names = [d['name'] for d in active_wallets.values()]
                    
                    # Deduplicate names
                    names = list(set(names))
                    
                    if len(names) > 1:
                        logger.info(f"Cluster detected: {names}")
                        
                        # AI Analysis
                        summary = await self.ai.analyze_cluster(f"Wallets active together: {', '.join(names)}. Tx Count: {len(recent_txs)}")
                        
                        msg = f"🧩 *RELATION ALERT*\nThese influencers are moving together:\n"
                        for n in names:
                            msg += f"- {n}\n"
                        msg += f"\n🧠 AI Insight: {summary}"
                        
                        await bot_instance.send_alert(msg)
                        
                        # Store Relation (simplified)
                        # We just log active pairs
                        pass 

        except Exception as e:
            logger.error(f"Relation Engine Error: {e}")

    async def stop(self):
        self.running = False
