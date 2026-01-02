"""
Base Chain (Coinbase L2) Tracker
Monitors EVM wallets on Base chain for memecoin activity.
"""
import asyncio
import logging
from web3 import AsyncWeb3
from sqlalchemy import select
from src.db.database import AsyncSessionLocal
from src.db.models import Wallet, Transaction
import os
from datetime import datetime, timezone
from src.analysis.transaction_filter import TransactionFilter, TransactionImportance
from src.bot.telegram_handler import bot_instance

logger = logging.getLogger(__name__)
tx_filter = TransactionFilter()

class BaseTracker:
    """Tracks wallets on Base chain (Coinbase L2)."""
    
    def __init__(self):
        # Base mainnet RPC
        self.rpc_url = os.getenv("BASE_RPC_URL", "https://mainnet.base.org")
        self.w3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(self.rpc_url))
        self.running = False
        self.chain_id = 8453  # Base mainnet
        
    async def initialize(self):
        """Initialize the tracker (connect to RPC)."""
        logger.info("Initializing Base Tracker...")
        try:
            is_connected = await self.w3.is_connected()
            if is_connected:
                chain_id = await self.w3.eth.chain_id
                logger.info(f"✅ Base RPC connected (Chain ID: {chain_id})")
            else:
                logger.error("❌ Base RPC connection failed")
        except Exception as e:
            logger.error(f"Base RPC connection error: {e}")
    
    async def scan_all_wallets(self):
        """Scan all BASE wallets for recent transactions."""
        stats = {
            "new_txs": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "skipped": 0
        }
        
        try:
            # Get current block
            current_block = await self.w3.eth.block_number
            
            # Scan last 1000 blocks (Base: ~2s/block * 1000 = ~33 minutes)
            start_block = max(0, current_block - 1000)
            
            logger.info(f"Scanning Base blocks {start_block} to {current_block}...")
            
            async with AsyncSessionLocal() as session:
                # Get all active BASE wallets
                stmt = select(Wallet).where(Wallet.chain == 'BASE', Wallet.is_active == True)
                result = await session.execute(stmt)
                wallets = result.scalars().all()
                watched = set(w.address.lower() for w in wallets)
                
                logger.info(f"Watching {len(wallets)} Base wallets...")
                
                if not wallets:
                    logger.info("No Base wallets configured yet")
                    return stats
                
                # Process blocks in batches for efficiency
                batch_size = 100
                for batch_start in range(start_block, current_block + 1, batch_size):
                    batch_end = min(batch_start + batch_size, current_block + 1)
                    
                    for block_num in range(batch_start, batch_end):
                        try:
                            block = await self.w3.eth.get_block(block_num, full_transactions=True)
                            
                            for tx in block['transactions']:
                                # Check if wallet is involved
                                from_addr = tx['from'].lower() if tx.get('from') else None
                                to_addr = tx['to'].lower() if tx.get('to') else None
                                
                                involved_wallet = None
                                if from_addr in watched:
                                    involved_wallet = from_addr
                                elif to_addr in watched:
                                    involved_wallet = to_addr
                                
                                if involved_wallet:
                                    # Find wallet ID
                                    stmt = select(Wallet).where(Wallet.address == involved_wallet)
                                    result = await session.execute(stmt)
                                    wallet = result.scalar_one_or_none()

                                    if not wallet:
                                        continue

                                    # Check if already tracked
                                    existing = await session.execute(
                                        select(Transaction).where(Transaction.tx_hash == tx['hash'].hex())
                                    )
                                    if existing.scalar_one_or_none():
                                        continue
                                    
                                    # New transaction
                                    stats["new_txs"] += 1
                                    
                                    # Save transaction
                                    new_tx = Transaction(
                                        wallet_id=wallet.id,
                                        tx_hash=tx['hash'].hex(),
                                        chain='BASE',
                                        block_number=block_num,
                                        timestamp=datetime.fromtimestamp(block['timestamp'], tz=timezone.utc),
                                        tx_type='TRANSFER',
                                        amount=float(tx['value']) / 1e18 if tx.get('value') else 0.0,
                                        token_symbol='ETH'
                                    )
                                    session.add(new_tx)
                                    
                                    logger.info(f"New Base tx for {wallet.name}: {tx['hash'].hex()[:16]}...")
                                    stats["medium"] += 1

                        except Exception as e:
                            logger.debug(f"Error processing Base block {block_num}: {e}")
                            continue
                    
                    # Commit batch
                    await session.commit()
                    await asyncio.sleep(0.1)  # Rate limiting
                        
        except Exception as e:
            logger.error(f"Error in Base scan: {e}")
        
        return stats
    
    async def stop(self):
        """Stop the tracker."""
        self.running = False
        logger.info("Base Tracker Stopped")
