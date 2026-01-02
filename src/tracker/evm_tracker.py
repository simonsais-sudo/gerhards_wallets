import asyncio
import logging
from web3 import AsyncWeb3
from sqlalchemy import select
from src.db.database import AsyncSessionLocal
from src.db.models import Wallet, Transaction
import os
from datetime import datetime, timezone
from src.bot.telegram_handler import bot_instance
from src.analysis.ai_analyzer import AIAnalyzer
from src.analysis.transaction_filter import TransactionFilter, TransactionImportance

logger = logging.getLogger(__name__)
ai_analyzer = AIAnalyzer()
tx_filter = TransactionFilter()


class EVMTracker:
    def __init__(self):
        self.rpc_url = os.getenv("ETH_RPC_URL", "https://eth.llamarpc.com")
        self.w3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(self.rpc_url))
        self.running = False
        self.watched_addresses = set()

    async def update_watched_addresses(self):
        async with AsyncSessionLocal() as session:
            stmt = select(Wallet.address).where(Wallet.chain == 'EVM', Wallet.is_active == True)
            result = await session.execute(stmt)
            # Normalizing addresses to checksum
            self.watched_addresses = {AsyncWeb3.to_checksum_address(addr) for addr in result.scalars().all()}
            logger.info(f"Updated EVM watched list: {len(self.watched_addresses)} addresses")

    async def poll_blocks(self):
        last_block = await self.w3.eth.block_number
        
        while self.running:
            try:
                current_block = await self.w3.eth.block_number
                if current_block > last_block:
                    for block_num in range(last_block + 1, current_block + 1):
                        await self.process_block(block_num)
                    last_block = current_block
                
                await asyncio.sleep(12) # Avg ETH block time
            except Exception as e:
                logger.error(f"Error in EVM block polling: {e}")
                await asyncio.sleep(5)

    async def process_block(self, block_num):
        try:
            # Get block with full transactions
            block = await self.w3.eth.get_block(block_num, full_transactions=True)
            
            async with AsyncSessionLocal() as session:
                for tx in block.transactions:
                    # check 'from'
                    # check 'to' (can be None for contract creation)
                    
                    is_hit = False
                    user_addr = None
                    
                    tx_from = tx.get('from')
                    tx_to = tx.get('to')

                    if tx_from and tx_from in self.watched_addresses:
                        is_hit = True
                        user_addr = tx_from
                    elif tx_to and tx_to in self.watched_addresses:
                        is_hit = True
                        user_addr = tx_to
                    
                    if is_hit:
                        # Find wallet ID
                        stmt = select(Wallet).where(Wallet.address == user_addr.lower())
                        result = await session.execute(stmt)
                        wallet = result.scalar_one_or_none()
                        
                        if wallet:
                            # Save Tx
                            existing = await session.execute(select(Transaction).where(Transaction.tx_hash == tx['hash'].hex()))
                            if not existing.scalar_one_or_none():
                                new_tx = Transaction(
                                    wallet_id=wallet.id,
                                    tx_hash=tx['hash'].hex(),
                                    chain='EVM',
                                    block_number=block_num,
                                    timestamp=datetime.fromtimestamp(block.timestamp, tz=timezone.utc),
                                    tx_type='TRANSFER'
                                )
                                session.add(new_tx)
                                logger.info(f"New EVM Tx for {wallet.name}: {tx['hash'].hex()}")
                                
                                # Assess transaction importance BEFORE AI analysis
                                importance, reason = tx_filter.assess_evm_transaction(tx, self.w3)
                                
                                logger.info(f"Transaction {tx['hash'].hex()[:16]}... classified as {importance.name}: {reason}")
                                
                                # Skip uninteresting transactions entirely
                                if importance == TransactionImportance.SKIP:
                                    logger.debug(f"Skipping alert for {tx['hash'].hex()[:16]}... - {reason}")
                                    continue  # Don't send any alert
                                
                                # For LOW importance, send basic alert without AI
                                if importance == TransactionImportance.LOW:
                                    analysis = f"📊 **Low Activity**\n{reason}\n\n_Skipped AI analysis for minor transaction._"
                                else:
                                    # MEDIUM and HIGH importance - run AI analysis
                                    try:
                                        # Fetch Historical Context (last 10 transactions for this wallet)
                                        hist_stmt = select(Transaction).where(
                                            Transaction.wallet_id == wallet.id
                                        ).order_by(Transaction.id.desc()).limit(10)
                                        hist_result = await session.execute(hist_stmt)
                                        history = hist_result.scalars().all()
                                        
                                        history_text = "No prior history."
                                        if history:
                                            history_lines = []
                                            for h in history:
                                                history_lines.append(f"- {h.tx_type}: {h.tx_hash[:16]}... (Block: {h.block_number})")
                                            history_text = "\n".join(history_lines)
                                        
                                        prompt = (
                                            f"Wallet: {wallet.name}\n"
                                            f"Current Tx: {tx['hash'].hex()}\n"
                                            f"Value: {self.w3.from_wei(tx['value'], 'ether')} ETH\n"
                                            f"Classification: {importance.name} - {reason}\n\n"
                                            f"**Historical Context (Last 10 Txs):**\n{history_text}\n\n"
                                            f"Analyze this transaction. Consider if there's a pattern (e.g., repeated buys, accumulation, dump). "
                                            f"Provide a short, sharp degen summary with sentiment (bullish/bearish/neutral)."
                                        )
                                        analysis = await ai_analyzer.analyze_transaction(wallet.name, prompt, relation_context="EVM On-Chain Data + History")
                                    except Exception as e:
                                        logger.error(f"AI Failed: {e}")
                                        analysis = f"⚠️ **{importance.name} Priority Transaction**\n{reason}\n\n_AI Analysis failed._"

                                # Broadcast Alert with importance context
                                await bot_instance.broadcast_alert(
                                    wallet_name=wallet.name,
                                    tx_hash=tx['hash'].hex(),
                                    chain='EVM',
                                    analysis=analysis,
                                    importance=importance.name
                                )

                
                await session.commit()
                
        except Exception as e:
            logger.error(f"Error processing EVM block {block_num}: {e}")

    async def start(self):
        self.running = True
        if await self.w3.is_connected():
            logger.info("Connected to EVM RPC")
            await self.update_watched_addresses()
            asyncio.create_task(self.poll_blocks())
            
            # Periodically refresh wallet list
            asyncio.create_task(self.refresh_wallets_periodically())
        else:
            logger.error("Failed to connect to EVM RPC")

    async def initialize(self):
        """Initialize the tracker (connect to RPC)."""
        logger.info("Initializing EVM Tracker...")
        try:
            if await self.w3.is_connected():
                logger.info("✅ EVM RPC connected")
                await self.update_watched_addresses()
            else:
                logger.error("EVM RPC connection failed")
        except Exception as e:
            logger.error(f"EVM initialization error: {e}")

    async def scan_all_wallets(self):
        """Scan all EVM wallets for recent transactions and return statistics."""
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
            
            # Scan last 300 blocks (approx 1 hour of history on Ethereum: 12s/block * 300 = 3600s)
            start_block = max(0, current_block - 300)
            
            logger.info(f"Scanning EVM blocks {start_block} to {current_block}...")
            
            async with AsyncSessionLocal() as session:
                # Get all active EVM wallets
                stmt = select(Wallet).where(Wallet.chain == 'EVM', Wallet.is_active == True)
                result = await session.execute(stmt)
                wallets = result.scalars().all()
                watched = set(w.address.lower() for w in wallets)
                
                logger.info(f"Watching {len(wallets)} EVM wallets...")
                
                # Process blocks
                for block_num in range(start_block, current_block + 1):
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
                                stmt = select(Wallet).where(Wallet.address == involved_wallet.lower())
                                result = await session.execute(stmt)
                                wallet = result.scalar_one_or_none() # Should exist

                                if not wallet:
                                    continue

                                # Check if already tracked
                                existing = await session.execute(
                                    select(Transaction).where(Transaction.tx_hash == tx['hash'].hex())
                                )
                                if existing.scalar_one_or_none():
                                    continue
                                
                                # Assess importance
                                importance, reason = tx_filter.assess_evm_transaction(tx, self.w3)
                                
                                if importance == TransactionImportance.SKIP:
                                    stats["skipped"] += 1
                                    continue

                                # New Transaction of interest
                                stats["new_txs"] += 1
                                if importance == TransactionImportance.HIGH:
                                    stats["high"] += 1
                                elif importance == TransactionImportance.MEDIUM:
                                    stats["medium"] += 1
                                elif importance == TransactionImportance.LOW:
                                    stats["low"] += 1

                                # Save Tx with actual on-chain timestamp
                                new_tx = Transaction(
                                    wallet_id=wallet.id,
                                    tx_hash=tx['hash'].hex(),
                                    chain='EVM',
                                    block_number=block_num,
                                    timestamp=datetime.fromtimestamp(block['timestamp'], tz=timezone.utc),
                                    tx_type='TRANSFER'
                                )
                                session.add(new_tx)

                                # Low importance: Basic alert
                                if importance == TransactionImportance.LOW:
                                    analysis = f"📊 **Low Activity**\n{reason}\n\n_Skipped AI analysis for minor transaction._"
                                else:
                                    # Medium/High: AI Analysis
                                    try:
                                        # History
                                        hist_stmt = select(Transaction).where(
                                            Transaction.wallet_id == wallet.id
                                        ).order_by(Transaction.id.desc()).limit(10)
                                        hist_result = await session.execute(hist_stmt)
                                        history = hist_result.scalars().all()
                                        
                                        history_text = "No prior history."
                                        if history:
                                            history_lines = []
                                            for h in history:
                                                history_lines.append(f"- {h.tx_type}: {h.tx_hash[:16]}... (Block: {h.block_number})")
                                            history_text = "\n".join(history_lines)
                                        
                                        prompt = (
                                            f"Wallet: {wallet.name}\n"
                                            f"Current Tx: {tx['hash'].hex()}\n"
                                            f"Value: {self.w3.from_wei(tx['value'], 'ether')} ETH\n"
                                            f"Classification: {importance.name} - {reason}\n\n"
                                            f"**Historical Context (Last 10 Txs):**\n{history_text}\n\n"
                                            f"Analyze this transaction. Consider if there's a pattern (e.g., repeated buys, accumulation, dump). "
                                            f"Provide a short, sharp degen summary with sentiment (bullish/bearish/neutral)."
                                        )
                                        analysis = await ai_analyzer.analyze_transaction(wallet.name, prompt, relation_context="EVM On-Chain Data + History")
                                    except Exception as e:
                                        logger.error(f"AI Failed: {e}")
                                        analysis = f"⚠️ **{importance.name} Priority Transaction**\n{reason}\n\n_AI Analysis failed._"

                                # Broadcast Alert
                                await bot_instance.broadcast_alert(
                                    wallet_name=wallet.name,
                                    tx_hash=tx['hash'].hex(),
                                    chain='EVM',
                                    analysis=analysis,
                                    importance=importance.name
                                )
                                    
                    except Exception as e:
                        logger.debug(f"Error processing block {block_num}: {e}")
                        continue
                
                # Commit all saved transactions
                await session.commit()
                        
        except Exception as e:
            logger.error(f"Error in EVM scan: {e}")
        
        return stats

    async def refresh_wallets_periodically(self):
        while self.running:
            await asyncio.sleep(300)
            await self.update_watched_addresses()

    async def stop(self):
        self.running = False
        logger.info("EVM Tracker Stopped")

