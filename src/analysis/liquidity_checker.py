
import aiohttp
import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class LiquidityChecker:
    """
    Checks token liquidity and market depth using Jupiter and Helius.
    Determines if an influencer dump will collapse the price.
    """
    
    JUPITER_QUOTE_URL = "https://quote-api.jup.ag/v6/quote"
    
    def __init__(self):
        self.helius_key = os.getenv("HELIUS_API_KEY")

    async def get_market_depth(self, token_address: str, input_amount_sol: float = 10.0) -> Dict[str, Any]:
        """
        Calculates price impact for a specific sell size.
        """
        if token_address == "So11111111111111111111111111111111111111112":
            return {"impact": 0.0, "status": "STABLE"}

        # Convert SOL to lamports (assuming 1 SOL input for impact test)
        # We test how much price moves if we sell X amount of the token
        # Actually, let's test selling 10 SOL worth of token back to SOL
        
        url = f"{self.JUPITER_QUOTE_URL}?inputMint={token_address}&outputMint=So11111111111111111111111111111111111111112&amount=1000000000&slippageBps=50"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        impact = float(data.get('priceImpactPct', 0))
                        
                        status = "HEALTHY"
                        if impact > 5: status = "THIN"
                        if impact > 15: status = "DANGEROUS"
                        
                        return {
                            "price_impact_pct": impact,
                            "status": status,
                            "out_amount": data.get('outAmount'),
                            "swap_path": "Jupiter"
                        }
        except Exception as e:
            logger.error(f"Liquidity check failed for {token_address}: {e}")
            
        return {"status": "UNKNOWN", "error": "API_ERROR"}

    async def assess_exit_risk(self, token_address: str, total_influencer_holdings_sol: float) -> Dict[str, Any]:
        """
        Compares influencer holdings to market depth.
        If influencers hold 50 SOL and 10 SOL sell = 10% impact, exit risk is EXTREME.
        """
        depth = await self.get_market_depth(token_address)
        
        if depth["status"] == "UNKNOWN":
            return {"risk": "UNKNOWN"}
            
        impact_per_sol = depth["price_impact_pct"] / 1.0 # Rough linear estimate if small
        total_potential_impact = impact_per_sol * total_influencer_holdings_sol
        
        risk_level = "LOW"
        if total_potential_impact > 20: risk_level = "MEDIUM"
        if total_potential_impact > 50: risk_level = "HIGH"
        if total_potential_impact > 80: risk_level = "CRITICAL (EXIT LIQUIDITY TRAP)"
        
        return {
            "token": token_address,
            "influencer_exposure_sol": total_influencer_holdings_sol,
            "est_dump_impact_pct": total_potential_impact,
            "risk_level": risk_level
        }

def format_liquidity_report(risk_data):
    """Formats liquidity findings for the bot/user."""
    return (
        f"💧 **LIQUIDITY ANALYSIS**\n"
        f"Token: `{risk_data['token'][:8]}...`\n"
        f"Influencer Exposure: `{risk_data['influencer_exposure_sol']:.2f} SOL`\n"
        f"Est. Dump Impact: `{risk_data['est_dump_impact_pct']:.1f}%`\n"
        f"Risk Level: **{risk_data['risk_level']}**\n\n"
        f"💡 {'BE CAREFUL: You are the exit liquidity.' if risk_data['est_dump_impact_pct'] > 30 else 'Safe to enter.'}"
    )
