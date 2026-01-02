
import asyncio
import os
import logging
from src.db.database import AsyncSessionLocal
from src.analysis.lead_follower import LeadFollowerEngine, format_gap_alert
from src.analysis.liquidity_checker import LiquidityChecker, format_liquidity_report
from src.analysis.stealth_discovery import StealthDiscovery, format_stealth_report
from src.service.alpha_gap_pusher import AlphaPusher

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AlphaPulse")

async def run_alpha_pulse(push_to_telegram=False):
    print("\n" + "="*60)
    print("🛰️ ALPHA PULSE v1.1: PROFIT & STEALTH HUB")
    print("="*60)
    
    async with AsyncSessionLocal() as session:
        # 1. Initialize Engines
        lead_follower = LeadFollowerEngine()
        liq_checker = LiquidityChecker()
        stealth_engine = StealthDiscovery()
        
        # 2. Find Air Gaps
        print("\n🔍 Scanning for Alpha Gaps (Frontrun Opportunities)...")
        gaps = await lead_follower.find_active_alpha_gaps(session)
        
        if not gaps:
            print("   No fresh Air Gaps detected.")
        else:
            for gap in gaps:
                print(f"\n[!] {format_gap_alert(gap)}")
                risk_data = await liq_checker.assess_exit_risk(gap['address'], 150.0) 
                print(f"   ∟ {format_liquidity_report(risk_data)}")

        # 3. Stealth Discovery
        print("\n🕵️ Running Stealth Discovery (Network Analysis)...")
        oracles = await stealth_engine.find_oracle_addresses(session)
        shadows = await stealth_engine.find_shadow_clusters(session)
        
        if oracles or shadows:
            print(format_stealth_report(oracles, shadows))
        else:
            print("   No new stealth oracles or shadow clusters detected.")

        # 4. Optional Push
        if push_to_telegram and gaps:
            print("\n📲 Pushing alerts to Telegram...")
            pusher = AlphaPusher()
            await pusher.push_latest_gaps()
        
    print("\n" + "="*60)
    print("✅ PULSE COMPLETE.")
    print("="*60 + "\n")

if __name__ == "__main__":
    import sys
    do_push = "--push" in sys.argv
    asyncio.run(run_alpha_pulse(push_to_telegram=do_push))
