"""
Jupiter Price API integration for fetching token prices.
"""
import aiohttp
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class PriceFetcher:
    """Fetches token prices from Jupiter Price API v2."""
    
    def __init__(self):
        self.base_url = "https://price.jup.ag/v6/price"
        self.cache = {}  # Simple in-memory cache
        
    async def get_price(self, token_address: str) -> Optional[float]:
        """
        Get USD price for a token.
        
        Args:
            token_address: Solana token mint address
            
        Returns:
            Price in USD or None if not found
        """
        if not token_address:
            return None
            
        # Check cache first
        if token_address in self.cache:
            return self.cache[token_address]
        
        try:
            url = f"{self.base_url}?ids={token_address}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        
                        if 'data' in data and token_address in data['data']:
                            price = data['data'][token_address].get('price')
                            if price:
                                self.cache[token_address] = float(price)
                                return float(price)
                        else:
                            logger.debug(f"No price data for {token_address}")
                            return None
                    else:
                        logger.warning(f"Price API returned {resp.status} for {token_address}")
                        return None
                        
        except Exception as e:
            logger.error(f"Error fetching price for {token_address}: {e}")
            return None
    
    async def get_prices_batch(self, token_addresses: list) -> Dict[str, float]:
        """
        Get prices for multiple tokens in one request.
        
        Args:
            token_addresses: List of token mint addresses
            
        Returns:
            Dict mapping address to price
        """
        if not token_addresses:
            return {}
        
        try:
            # Jupiter API supports comma-separated IDs
            ids = ",".join(token_addresses[:100])  # Max 100 at a time
            url = f"{self.base_url}?ids={ids}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        
                        prices = {}
                        if 'data' in data:
                            for addr in token_addresses:
                                if addr in data['data']:
                                    price = data['data'][addr].get('price')
                                    if price:
                                        prices[addr] = float(price)
                                        self.cache[addr] = float(price)
                        
                        return prices
                    else:
                        logger.warning(f"Batch price API returned {resp.status}")
                        return {}
                        
        except Exception as e:
            logger.error(f"Error fetching batch prices: {e}")
            return {}
    
    async def get_usd_value(self, token_address: str, amount: float) -> Optional[float]:
        """
        Calculate USD value of a token amount.
        
        Args:
            token_address: Token mint address
            amount: Token amount
            
        Returns:
            USD value or None
        """
        price = await self.get_price(token_address)
        if price:
            return price * amount
        return None
    
    def clear_cache(self):
        """Clear the price cache."""
        self.cache = {}

# Global instance
price_fetcher = PriceFetcher()
