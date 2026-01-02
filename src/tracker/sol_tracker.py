import asyncio
import logging
from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey
from sqlalchemy import select
from src.db.database import AsyncSessionLocal
from src.db.models import Wallet, Transaction
import os
import aiohttp
from datetime import datetime, timezone
from sqlalchemy.sql import func
from src.bot.telegram_handler import bot_instance
from src.analysis.ai_analyzer import AIAnalyzer
from src.analysis.transaction_filter import TransactionFilter, TransactionImportance
from src.analysis.pattern_engine import PatternEngine
from src.analysis.predictive_engine import PredictiveEngine
from src.analysis.cabal_detector import CabalDetector
from src.analysis.contrarian_engine import ContrarianEngine
from src.analysis.price_fetcher import price_fetcher

logger = logging.getLogger(__name__)
ai_analyzer = AIAnalyzer()
tx_filter = TransactionFilter()


class SolanaTracker:
    def __init__(self):
        # Support multiple RPCs comma-separated for rotation
        self.rpc_urls = os.getenv("HELIUS_RPC_URL", "").split(',')
        # Add the secondary key hardcoded if not in env to ensure it's used immediately without redeploying env file
        secondary_url = "https://mainnet.helius-rpc.com/?api-key=44dcc352-2b53-4423-9728-be0e510658a5"
        if secondary_url not in self.rpc_urls:
            self.rpc_urls.append(secondary_url)
            
        self.clients = [AsyncClient(url.strip()) for url in self.rpc_urls if url.strip()]
        self.current_client_idx = 0
        self.token_cache = {}
        self.running = False
        self.pattern_engine = PatternEngine()
        self.predictive_engine = PredictiveEngine()
        self.cabal_detector = CabalDetector()
        self.contrarian_engine = ContrarianEngine()


    def get_client(self):
        """Round-robin client selection"""
        if not self.clients:
            return None
        client = self.clients[self.current_client_idx]
        self.current_client_idx = (self.current_client_idx + 1) % len(self.clients)
        return client

    async def get_token_metadata(self, mint_address):
        """Fetch token metadata (symbol/name) using Helius DAS API."""
        if not mint_address:
            return "SOL"
            
        if mint_address in self.token_cache:
            return self.token_cache[mint_address]
        
        try:
            # Use current RPC for metadata
            url = self.rpc_urls[0].strip() 
            
            payload = {
                "jsonrpc": "2.0",
                "id": "token-lookup",
                "method": "getAsset",
                "params": {
                    "id": mint_address
                }
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        if 'result' in data:
                            content = data['result'].get('content', {})
                            metadata = content.get('metadata', {})
                            symbol = metadata.get('symbol', '').strip()
                            name = content.get('metadata', {}).get('name', '').strip()
                            
                            # Fallback if empty
                            if not symbol: 
                                symbol = "UNKNOWN"
                            
                            info = f"${symbol}"
                            self.token_cache[mint_address] = info
                            return info
        except Exception as e:
            logger.warning(f"Metadata lookup failed for {mint_address}: {e}")
            
        # Fallback to short addr
        return f"{mint_address[:4]}...{mint_address[-4:]}"

    async def poll_wallets(self):
        while self.running:
            try:
                async with AsyncSessionLocal() as session:
                    # Get all active SOL wallets
                    stmt = select(Wallet).where(Wallet.chain == 'SOL', Wallet.is_active == True)
                    result = await session.execute(stmt)
                    wallets = result.scalars().all()

                    for wallet in wallets:
                        await self.check_wallet(session, wallet)
                        await asyncio.sleep(0.5) # Rate limit protection
                
                await asyncio.sleep(30) # Poll every 30s
            except Exception as e:
                logger.error(f"Error in Solana polling loop: {e}")
                await asyncio.sleep(10)

    async def check_wallet(self, session, wallet):
        try:
            pubkey = Pubkey.from_string(wallet.address)
            # Get last 50 signatures (increased for hourly scan coverage)
            client = self.get_client()
            resp = await client.get_signatures_for_address(pubkey, limit=50)
            
            if not resp.value:
                return
            
            # Check if this wallet has ANY history in DB
            has_history = (await session.execute(select(Transaction).where(Transaction.wallet_id == wallet.id))).first() is not None

            for sig_info in resp.value:
                sig = str(sig_info.signature)
                
                # Check if exists
                existing = await session.execute(select(Transaction).where(Transaction.tx_hash == sig))
                if existing.scalar_one_or_none():
                    continue
                
                # Fetch detailed tx
                tx_resp = await client.get_transaction(sig_info.signature, max_supported_transaction_version=0)
                
                if not tx_resp.value:
                    continue

                # Parse Balance Changes for AI Context & DB Population
                balance_changes_text = "No balance changes detected."
                
                # DB Fields
                db_tx_type = 'UNKNOWN'
                db_amount = 0.0
                db_symbol = None
                db_token_addr = None
                
                try:
                    meta = tx_resp.value.transaction.meta
                    if meta:
                        changes = []
                        # 1. SOL Changes
                        # Check wallet's own SOL balance change
                        # Wallet index is usually 0 if they paid fee, but we must find their index
                        account_keys = tx_resp.value.transaction.transaction.message.account_keys
                        wallet_pubkey_str = str(wallet.address)
                        
                        sol_diff = 0.0
                        try:
                            # Convert Solders Pubkey objects to strings for comparison
                            # account_keys can be list of Pubkey objects
                            acct_indices = [str(k) for k in account_keys]
                            if wallet_pubkey_str in acct_indices:
                                idx = acct_indices.index(wallet_pubkey_str)
                                pre_sol = meta.pre_balances[idx] / 1e9
                                post_sol = meta.post_balances[idx] / 1e9
                                sol_diff = post_sol - pre_sol
                                if abs(sol_diff) > 0.001:
                                    changes.append(f"SOL: {sol_diff:+.4f}")
                                    # Default to TRANSFER if no token found later
                                    db_tx_type = 'TRANSFER'
                                    db_amount = abs(sol_diff)
                                    db_symbol = 'SOL'
                        except Exception as e:
                            logger.warn(f"Failed to calc SOL diff: {e}")

                        # 2. Token Changes
                        if meta.pre_token_balances is not None and meta.post_token_balances is not None:
                            # Filter for our wallet
                            target_owner = str(wallet.address)
                            
                            pre_map = {} # (mint) -> amount
                            for b in meta.pre_token_balances:
                                if str(b.owner) == target_owner:
                                    pre_map[str(b.mint)] = b.ui_token_amount.ui_amount or 0.0

                            # Track tokens gained vs lost for BUY/SELL detection
                            tokens_gained = []
                            tokens_lost = []
                            
                            for b in meta.post_token_balances:
                                if str(b.owner) == target_owner:
                                    mint = str(b.mint)
                                    post_amt = b.ui_token_amount.ui_amount or 0.0
                                    pre_amt = pre_map.get(mint, 0.0)
                                    
                                    diff = post_amt - pre_amt
                                    
                                    # Filter noise (dust)
                                    if abs(diff) > 0.000001:
                                        # Get Symbol
                                        symbol = await self.get_token_metadata(mint)
                                        symbol_clean = symbol.replace('$','').strip()
                                        changes.append(f"{symbol}: {diff:+.4f}")
                                        
                                        if diff > 0:
                                            tokens_gained.append((symbol_clean, mint, diff))
                                        else:
                                            tokens_lost.append((symbol_clean, mint, abs(diff)))
                            
                            # SELL/BUY Classification Logic (ENHANCED):
                            # - SELL = Lost a token AND gained SOL/USDC/USDT (or more SOL)
                            # - BUY = Lost SOL/USDC/USDT AND gained a token (or less SOL)
                            # - SWAP = Token A → Token B (both non-stables)
                            stables = {'SOL', 'USDC', 'USDT', 'wSOL', 'WSOL', 'USDC.e', 'USDCet'}
                            
                            # Debug logging
                            logger.debug(f"Tokens gained: {[t[0] for t in tokens_gained]}, Tokens lost: {[t[0] for t in tokens_lost]}, SOL diff: {sol_diff}")
                            
                            if tokens_lost and tokens_gained:
                                # Check what we gained - if stable, it's a SELL
                                gained_stables = [t for t in tokens_gained if t[0] in stables]
                                gained_tokens = [t for t in tokens_gained if t[0] not in stables]
                                lost_stables = [t for t in tokens_lost if t[0] in stables]
                                lost_tokens = [t for t in tokens_lost if t[0] not in stables]
                                
                                # IMPROVED: Check for sells more aggressively
                                if lost_tokens and (gained_stables or sol_diff > 0.001):
                                    # SELL: Lost a token, gained SOL/stable (even small amounts)
                                    db_tx_type = 'SELL'
                                    db_symbol = lost_tokens[0][0]
                                    db_token_addr = lost_tokens[0][1]
                                    db_amount = lost_tokens[0][2]
                                    logger.info(f"🔴 SELL DETECTED: {db_amount:.4f} {db_symbol} → SOL/stable")
                                elif gained_tokens and (lost_stables or sol_diff < -0.001):
                                    # BUY: Lost SOL/stable, gained a token
                                    db_tx_type = 'BUY'
                                    db_symbol = gained_tokens[0][0]
                                    db_token_addr = gained_tokens[0][1]
                                    db_amount = gained_tokens[0][2]
                                    logger.info(f"🟢 BUY DETECTED: {db_amount:.4f} {db_symbol}")
                                elif lost_tokens and gained_tokens:
                                    # Token-to-token swap (e.g., BONK → WIF)
                                    db_tx_type = 'SWAP'
                                    # Prioritize the gained token as the "main" one
                                    db_symbol = gained_tokens[0][0]
                                    db_token_addr = gained_tokens[0][1]
                                    db_amount = gained_tokens[0][2]
                                    logger.info(f"🔄 SWAP DETECTED: {lost_tokens[0][0]} → {db_symbol}")
                            elif tokens_gained and not tokens_lost and sol_diff < -0.001:
                                # Pure buy: Only lost SOL, gained token
                                db_tx_type = 'BUY'
                                non_stables = [t for t in tokens_gained if t[0] not in stables]
                                if non_stables:
                                    db_symbol = non_stables[0][0]
                                    db_token_addr = non_stables[0][1]
                                    db_amount = non_stables[0][2]
                                    logger.info(f"🟢 PURE BUY: {db_amount:.4f} {db_symbol}")
                            elif tokens_lost and not tokens_gained and sol_diff > 0.001:
                                # Pure sell: Lost token, only gained SOL
                                db_tx_type = 'SELL'
                                non_stables = [t for t in tokens_lost if t[0] not in stables]
                                if non_stables:
                                    db_symbol = non_stables[0][0]
                                    db_token_addr = non_stables[0][1]
                                    db_amount = non_stables[0][2]
                                    logger.info(f"🔴 PURE SELL: {db_amount:.4f} {db_symbol} → SOL")
                            elif tokens_lost and not tokens_gained:
                                # Edge case: Lost token but SOL didn't increase (might be wrapped/unwrapped)
                                # Still count as SELL
                                non_stables = [t for t in tokens_lost if t[0] not in stables]
                                if non_stables:
                                    db_tx_type = 'SELL'
                                    db_symbol = non_stables[0][0]
                                    db_token_addr = non_stables[0][1]
                                    db_amount = non_stables[0][2]
                                    logger.info(f"🔴 SELL (edge case): {db_amount:.4f} {db_symbol}")

                        if changes:
                            balance_changes_text = ", ".join(changes)
                except Exception as e:
                    logger.error(f"Balance parsing error: {e}")

                # Get ACTUAL on-chain timestamp (not scan time)
                block_time = tx_resp.value.block_time
                if block_time:
                    tx_timestamp = datetime.fromtimestamp(block_time, tz=timezone.utc)
                else:
                    tx_timestamp = datetime.now(timezone.utc)  # Fallback

                # Fetch USD value if we have a token address
                usd_value = None
                if db_token_addr and db_amount:
                    try:
                        usd_value = await price_fetcher.get_usd_value(db_token_addr, db_amount)
                        if usd_value:
                            logger.info(f"💰 USD Value: ${usd_value:,.2f}")
                    except Exception as e:
                        logger.debug(f"Could not fetch price for {db_symbol}: {e}")

                new_tx = Transaction(
                    wallet_id=wallet.id,
                    tx_hash=sig,
                    chain='SOL',
                    block_number=tx_resp.value.slot,
                    timestamp=tx_timestamp,
                    tx_type=db_tx_type,
                    amount=db_amount,
                    amount_usd=usd_value,
                    token_symbol=db_symbol,
                    token_address=db_token_addr
                )
                session.add(new_tx)
                # Flush to get ID for pattern engine usage
                await session.flush()
                
                logger.info(f"New SOL Tx for {wallet.name}: {sig} ({db_tx_type} {db_symbol})")
                
                # === PREDICTIVE ENGINE ===
                # 1. Detect Reloads (incoming SOL)
                if db_tx_type == 'TRANSFER' and db_symbol == 'SOL' and sol_diff > 0:
                    reload_result = await self.predictive_engine.detect_reload(
                        session, wallet, new_tx, sol_diff
                    )
                    if reload_result:
                        logger.info(f"🔮 PREDICTION: {reload_result['prediction']['message']}")
                
                # 2. Resolve Predictions (when a buy happens)
                if db_tx_type in ('BUY', 'SWAP'):
                    await self.predictive_engine.check_reload_resolution(session, wallet, new_tx)
                    
                    # === CABAL DETECTION ===
                    cabal_result = await self.cabal_detector.detect_cluster_buy(
                        session, wallet, db_symbol, db_token_addr
                    )
                    if cabal_result:
                        logger.info(f"🕸️ CABAL: {cabal_result['cluster_size']} wallets on ${db_symbol}")
                    
                    # === CONTRARIAN ENGINE ===
                    contrarian_signals = await self.contrarian_engine.check_for_contrarian_on_buy(
                        session, wallet, db_symbol, db_token_addr
                    )
                    if contrarian_signals:
                        for signal in contrarian_signals:
                            logger.warning(f"🔄 CONTRARIAN: {signal['type']} on ${db_symbol}")
                
                # 3. Log sells and check contrarian on sells too
                if db_tx_type == 'SELL':
                    logger.info(f"📉 SELL detected: {wallet.name} sold {db_amount:.4f} {db_symbol}")
                    
                    # Check if this sell triggers contrarian signals
                    contrarian_signals = await self.contrarian_engine.analyze_token_activity(
                        session, db_symbol, db_token_addr
                    )
                    if contrarian_signals:
                        for signal in contrarian_signals:
                            if signal['type'] == 'SMART_MONEY_EXIT':
                                logger.warning(f"🚨 CRITICAL: {signal['message'][:80]}...")
                
                # Pattern Analysis (existing)
                pattern_alert = await self.pattern_engine.analyze_behavior(session, wallet, new_tx)
                if pattern_alert:
                    logger.info(f"Pattern Detected: {pattern_alert}")
                
                
                # Only process if we already had history (active tracking)
                if has_history:
                    # Pattern detected - log it but DON'T send automatic alert
                    # Users will access insights on-demand via /report, /txs commands
                    if pattern_alert:
                        logger.info(f"Pattern Detected (stored): {pattern_alert[:50]}...")
                        # Pattern is already saved to Moments table by pattern_engine
                    
                    # Classify for logging purposes only
                    importance, reason = tx_filter.assess_solana_transaction(tx_resp.value, wallet.address)
                    logger.info(f"Transaction {sig[:16]}... classified as {importance.name}: {reason} (Data collected)")

            
            await session.commit()
            return None
            
        except Exception as e:
            logger.error(f"Error checking SOL wallet {wallet.address}: {e}")
            return None

    async def initialize(self):
        """Initialize the tracker (connect to RPC)."""
        logger.info("Initializing Solana Tracker...")
        try:
            # Test connections
            for client in self.clients:
                await client.is_connected()
            logger.info("✅ All Solana RPCs connected")
        except Exception as e:
            logger.error(f"Solana RPC connection failed: {e}")

    async def scan_all_wallets(self):
        """Scan all wallets once and return statistics."""
        stats = {
            "new_txs": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "skipped": 0
        }
        
        try:
            async with AsyncSessionLocal() as session:
                # Get all active SOL wallets
                stmt = select(Wallet).where(Wallet.chain == 'SOL', Wallet.is_active == True)
                result = await session.execute(stmt)
                wallets = result.scalars().all()
                
                logger.info(f"Scanning {len(wallets)} Solana wallets...")
                
                for wallet in wallets:
                    importance = await self.check_wallet(session, wallet)
                    if importance:
                        stats["new_txs"] += 1
                        if importance == TransactionImportance.HIGH:
                            stats["high"] += 1
                        elif importance == TransactionImportance.MEDIUM:
                            stats["medium"] += 1
                        elif importance == TransactionImportance.LOW:
                            stats["low"] += 1
                        else:
                            stats["skipped"] += 1
                    await asyncio.sleep(0.3)  # Rate limit protection
                
                await session.commit()
                    
        except Exception as e:
            logger.error(f"Error in Solana scan: {e}")
        
        return stats

    async def start(self):
        """Start continuous polling mode (legacy)."""
        self.running = True
        asyncio.create_task(self.poll_wallets())
        logger.info("Solana Tracker Started (Continuous Mode)")

    async def stop(self):
        self.running = False
        for client in self.clients:
            await client.close()
        logger.info("Solana Tracker Stopped")

