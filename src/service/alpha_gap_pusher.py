
import asyncio
import logging
from src.bot.telegram_handler import TelegramBot
from src.db.database import AsyncSessionLocal
from src.analysis.lead_follower import LeadFollowerEngine, format_gap_alert
from src.analysis.liquidity_checker import LiquidityChecker, format_liquidity_report

logger = logging.getLogger(__name__)

class AlphaPusher:
    """
    Service to push high-confidence Alpha Gaps to Telegram.
    """
    def __init__(self):
        self.bot = TelegramBot()
        self.lead_engine = LeadFollowerEngine()
        self.liq_checker = LiquidityChecker()

    async def push_latest_gaps(self):
        """
        Scans for gaps and pushes to the configured admin chat.
        """
        if not self.bot.bot:
            print("Telegram Bot not initialized. Check TELEGRAM_TOKEN.")
            return

        async with AsyncSessionLocal() as session:
            gaps = await self.lead_engine.find_active_alpha_gaps(session)
            
            if not gaps:
                print("No fresh Alpha Gaps to push.")
                return

            for gap in gaps:
                # Assess Risk
                risk = await self.liq_checker.assess_exit_risk(gap['address'], 150.0)
                
                # Only push if risk is not CRITICAL
                if "CRITICAL" not in risk['risk_level']:
                    alert = format_gap_alert(gap)
                    liq_alert = format_liquidity_report(risk)
                    
                    full_message = f"{alert}\n\n{liq_alert}"
                    
                    print(f"Pushing alert for {gap['symbol']}...")
                    await self.bot.send_alert(full_message)
                else:
                    print(f"Skipping push for {gap['symbol']} - Too risky.")

if __name__ == "__main__":
    pusher = AlphaPusher()
    asyncio.run(pusher.push_latest_gaps())
