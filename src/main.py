import asyncio
import os
import json
import logging
from datetime import datetime
from dotenv import load_dotenv

from src.db.database import init_db, AsyncSessionLocal
from src.db.models import Wallet
from sqlalchemy import select

# Load environment
load_dotenv()

# Logger setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
SCAN_INTERVAL_SECONDS = 300  # 5 minutes

async def load_initial_wallets():
    """Loads wallets from config/wallets.json into the DB if they don't exist."""
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'wallets.json')
    if not os.path.exists(config_path):
        logger.warning(f"Config file not found at {config_path}")
        return

    with open(config_path, 'r') as f:
        wallets_data = json.load(f)

    async with AsyncSessionLocal() as session:
        for w_data in wallets_data:
            # Check if exists
            stmt = select(Wallet).where(Wallet.address == w_data['address'])
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            
            if not existing:
                try:
                    conf = int(w_data.get('confidence', 0))
                except:
                    conf = 0
                
                new_wallet = Wallet(
                    address=w_data['address'],
                    name=w_data['name'],
                    chain=w_data.get('chain', 'EVM'), # Default to EVM
                    confidence_score=conf
                )
                session.add(new_wallet)
                logger.info(f"Added new wallet: {w_data['name']} ({w_data['address']})")
        
        await session.commit()

async def run_hourly_scan(sol_tracker, evm_tracker, bot_instance):
    """Run a complete scan of all wallets and send summary."""
    scan_start = datetime.now()
    logger.info(f"🔍 Starting hourly scan at {scan_start.strftime('%H:%M:%S')}")
    
    # Track statistics
    stats = {
        "sol_new_txs": 0,
        "evm_new_txs": 0,
        "high_priority": 0,
        "medium_priority": 0,
        "skipped": 0
    }
    
    try:
        # Scan Solana wallets
        logger.info("Scanning Solana wallets...")
        sol_stats = await sol_tracker.scan_all_wallets()
        if sol_stats:
            stats["sol_new_txs"] = sol_stats.get("new_txs", 0)
            stats["high_priority"] += sol_stats.get("high", 0)
            stats["medium_priority"] += sol_stats.get("medium", 0)
            stats["skipped"] += sol_stats.get("skipped", 0)
        
        # Scan EVM wallets  
        logger.info("Scanning EVM wallets...")
        evm_stats = await evm_tracker.scan_all_wallets()
        if evm_stats:
            stats["evm_new_txs"] = evm_stats.get("new_txs", 0)
            stats["high_priority"] += evm_stats.get("high", 0)
            stats["medium_priority"] += evm_stats.get("medium", 0)
            stats["skipped"] += evm_stats.get("skipped", 0)
        
        scan_end = datetime.now()
        duration = (scan_end - scan_start).seconds
        
        # Log summary
        total_txs = stats["sol_new_txs"] + stats["evm_new_txs"]
        logger.info(f"✅ Scan complete in {duration}s: {total_txs} new transactions")
        logger.info(f"   HIGH: {stats['high_priority']} | MEDIUM: {stats['medium_priority']} | SKIPPED: {stats['skipped']}")
        
        # === AI PLAY FINDER ===
        # Run AI analysis to find actionable plays
        try:
            from src.analysis.play_finder import PlayFinder, format_play_alert
            from src.db.database import AsyncSessionLocal
            
            async with AsyncSessionLocal() as session:
                finder = PlayFinder(session)
                plays = await finder.find_plays()
                
                if plays:
                    logger.info(f"🎯 AI found {len(plays)} potential plays!")
                    for play in plays[:3]:  # Max 3 alerts per scan
                        alert = format_play_alert(play)
                        await bot_instance.send_alert(alert)
                else:
                    logger.info("🔍 No plays found this scan.")
                    
        except Exception as e:
            logger.error(f"Play finder error: {e}")
        
        # Send scan summary (only if significant activity)
        if stats["high_priority"] > 0 or stats["medium_priority"] > 0:
            summary_msg = (
                f"📊 *Scan Summary*\n"
                f"🕐 {scan_start.strftime('%H:%M')} - {scan_end.strftime('%H:%M')}\n\n"
                f"*New Activity:*\n"
                f"• SOL: {stats['sol_new_txs']} transactions\n"
                f"• EVM: {stats['evm_new_txs']} transactions\n\n"
                f"*Priority:*\n"
                f"🔥 High: {stats['high_priority']}\n"
                f"⚡ Medium: {stats['medium_priority']}\n"
                f"⏭️ Skipped: {stats['skipped']}\n\n"
                f"_Next scan in {SCAN_INTERVAL_SECONDS // 60} min._"
            )
            await bot_instance.send_alert(summary_msg)
        
    except Exception as e:
        logger.error(f"Error during scan: {e}")

async def main():
    logger.info("=" * 60)
    logger.info("🚀 Starting Influencer Tracker Bot (Live Mode)")
    logger.info(f"   Scan interval: {SCAN_INTERVAL_SECONDS // 60} minutes")
    logger.info("=" * 60)
    
    # Init DB
    await init_db()
    
    # Load Wallets
    await load_initial_wallets()
    
    # Init Trackers
    from src.tracker.sol_tracker import SolanaTracker
    from src.tracker.evm_tracker import EVMTracker
    from src.bot.telegram_handler import bot_instance
    
    sol_tracker = SolanaTracker()
    evm_tracker = EVMTracker()
    
    # Initialize trackers (connect to RPCs)
    await sol_tracker.initialize()
    await evm_tracker.initialize()
    
    # Start Bot (runs in background)
    asyncio.create_task(bot_instance.start())
    
    logger.info("✅ All services initialized. Starting hourly scan loop...")
    
    # Send startup notification
    await bot_instance.send_alert(
        "🟢 *Influencer Tracker Online*\n\n"
        f"Mode: *Live Scanning*\n"
        f"Interval: Every {SCAN_INTERVAL_SECONDS // 60} minutes\n\n"
        "_First scan starting now..._"
    )
    
    try:
        # Run first scan immediately
        await run_hourly_scan(sol_tracker, evm_tracker, bot_instance)
        
        # Then run every hour
        while True:
            logger.info(f"⏳ Waiting {SCAN_INTERVAL_SECONDS // 60} minutes until next scan...")
            await asyncio.sleep(SCAN_INTERVAL_SECONDS)
            await run_hourly_scan(sol_tracker, evm_tracker, bot_instance)
            
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        await sol_tracker.stop()
        await evm_tracker.stop()

if __name__ == "__main__":
    asyncio.run(main())

