import logging
import os
from datetime import datetime, timezone, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from sqlalchemy import select, func, desc
from src.db.database import AsyncSessionLocal
from src.db.models import Wallet, Moment, User, WalletStats, Transaction, ReloadEvent
from src.bot.payment import payment_verifier, TREASURY_SOL, PRICE_SOL_COPY_TRADER, PRICE_SOL_RESEARCHER

logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self):
        token = os.getenv("TELEGRAM_TOKEN")
        
        self.config_path = "config/bot_config.json"
        
        if not token:
            logger.error("TELEGRAM_TOKEN not set")
            self.bot = None
            return
            
        self.bot = Bot(token=token)
        self.dp = Dispatcher()
        self.admin_chat_id = self.load_chat_id()

        # Register handlers
        self.dp.message(Command("start"))(self.cmd_start)
        self.dp.message(Command("status"))(self.cmd_status)
        self.dp.message(Command("check"))(self.cmd_check)
        self.dp.message(Command("upgrade"))(self.cmd_upgrade)
        self.dp.message(Command("verify"))(self.cmd_verify_payment)
        self.dp.message(Command("report"))(self.cmd_report)
        self.dp.message(Command("influencers"))(self.cmd_influencers)
        self.dp.message(Command("txs"))(self.cmd_txs)
        self.dp.message(Command("insights"))(self.cmd_insights)
        self.dp.message(Command("predictions"))(self.cmd_predictions)
        self.dp.message(Command("cabals"))(self.cmd_cabals)
        self.dp.message(Command("link_twitter"))(self.cmd_link_twitter)
    
    # ... (skipping to cmd_alpha) 

    async def cmd_alpha(self, message: types.Message):
        """Show alpha leaderboard - who has the freshest edge?"""
        async with AsyncSessionLocal() as session:
            try:
                # 1. Proven Alpha (Trades Analyzed > 0)
                stmt_proven = (
                    select(Wallet.name, WalletStats.alpha_score, WalletStats.avg_copiers_per_trade, WalletStats.win_rate)
                    .join(WalletStats, Wallet.id == WalletStats.wallet_id)
                    .where(WalletStats.trades_analyzed > 0)
                    .order_by(desc(WalletStats.alpha_score))
                    .limit(5)
                )
                proven = (await session.execute(stmt_proven)).all()
                
                # 2. Potential Alpha (High Activity, No Closed Trades yet)
                stmt_potential = (
                    select(Wallet.name, WalletStats.total_tx_count)
                    .join(WalletStats, Wallet.id == WalletStats.wallet_id)
                    .where(WalletStats.trades_analyzed == 0)
                    .where(WalletStats.total_tx_count > 0)
                    .order_by(desc(WalletStats.total_tx_count))
                    .limit(5)
                )
                potential = (await session.execute(stmt_potential)).all()
                
                text = "🔥 *ALPHA LEADERBOARD*\n"
                text += "_Highest = Least crowded edge_\n\n"
                
                if not proven and not potential:
                    text += "_No data yet. Waiting for moves._"
                else:
                    if proven:
                        text += "*🏆 Proven Edge:*\n"
                        for i, (name, alpha, copiers, win_rate) in enumerate(proven, 1):
                            short_name = name[:18] + "..." if len(name) > 18 else name
                            if alpha >= 80: emoji = "🔥"
                            elif alpha >= 60: emoji = "✅"
                            elif alpha >= 40: emoji = "⚠️"
                            else: emoji = "❄️"
                            
                            copier_text = f"{copiers:.1f}" if copiers else "0"
                            win_text = f"{win_rate*100:.0f}%" if win_rate is not None else "??"
                            text += f"{i}. {emoji} *{short_name}*\n"
                            text += f"   Alpha: {alpha:.0f} | Copiers: {copier_text} | Win: {win_text}\n"
                        text += "\n"

                    if potential:
                        text += "*⚡ active & Learning:*\n"
                        for i, (name, tx_count) in enumerate(potential, 1):
                            short_name = name[:18] + "..." if len(name) > 18 else name
                            text += f"• *{short_name}*\n"
                            text += f"   📊 {tx_count} live txs (waiting for exit)\n"
                
                text += "\n_Lower copiers = fresher alpha_"
                await message.answer(text, parse_mode="Markdown")
                
            except Exception as e:
                logger.error(f"Alpha cmd error: {e}")
                await message.answer(f"❌ Error: {e}")

    async def cmd_link_twitter(self, message: types.Message):
        """Link a wallet to a Twitter handle."""
        args = message.text.split()
        if len(args) < 3:
            await message.answer(
                "🔗 *Link Twitter Handle*\n\n"
                "Usage: `/link_twitter <wallet_name> <@handle>`\n"
                "Example: `/link_twitter Murad @MustStopMurad`"
            , parse_mode="Markdown")
            return
            
        search_name = args[1]
        handle = args[2].replace("@", "")
        
        async with AsyncSessionLocal() as session:
            try:
                # Find wallet
                stmt = select(Wallet).where(Wallet.name.ilike(f"%{search_name}%")).limit(1)
                result = await session.execute(stmt)
                wallet = result.scalar_one_or_none()
                
                if not wallet:
                    await message.answer(f"❌ Wallet with name containing '{search_name}' not found.")
                    return
                    
                wallet.twitter_handle = handle
                await session.commit()
                
                await message.answer(f"✅ Linked *{wallet.name}* to None*@{handle}*", parse_mode="Markdown")
                
            except Exception as e:
                logger.error(f"Link Twitter error: {e}")
                await message.answer(f"❌ Error: {e}")

    def load_chat_id(self):
        try:
            import json
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    data = json.load(f)
                    cid = data.get("admin_chat_id")
                    if cid:
                        logger.info(f"Loaded Chat ID: {cid}")
                        return cid
        except Exception as e:
            logger.error(f"Error loading chat ID: {e}")
        return None

    def save_chat_id(self, chat_id):
        try:
            import json
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump({"admin_chat_id": chat_id}, f)
            logger.info(f"Saved Chat ID: {chat_id}")
        except Exception as e:
            logger.error(f"Error saving chat ID: {e}")

    async def start(self):
        if self.bot:
            logger.info("Starting Telegram Bot Polling...")
            await self.dp.start_polling(self.bot)

    async def send_alert(self, message: str):
        """Send a notification to the admin chat."""
        if not self.admin_chat_id:
            logger.warning("No admin chat ID set - cannot send alert")
            return
        
        try:
            await self.bot.send_message(
                chat_id=self.admin_chat_id,
                text=message,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")

    async def cmd_start(self, message: types.Message):
        self.admin_chat_id = message.chat.id
        self.save_chat_id(self.admin_chat_id)
        
        # Register User in DB and fetch wallet stats
        async with AsyncSessionLocal() as session:
            try:
                # Check if user exists
                user = await session.get(User, message.chat.id)
                if not user:
                    user = User(chat_id=message.chat.id, username=message.from_user.username, access_level="RESEARCHER")
                    session.add(user)
                    await session.commit()
                    logger.info(f"Registered new user: {message.chat.id} as RESEARCHER")
                else:
                    # Auto-upgrade existing users to RESEARCHER (No Payments Mode)
                    if user.access_level != "RESEARCHER":
                        user.access_level = "RESEARCHER"
                        await session.commit()
                        logger.info(f"Upgraded existing user {message.chat.id} to RESEARCHER")
                    else:
                        logger.info(f"User already registered: {message.chat.id}")
                    
                # Fetch all wallets grouped by influencer
                stmt = select(Wallet).where(Wallet.is_active == True).order_by(Wallet.name)
                result = await session.execute(stmt)
                wallets = result.scalars().all()
                
                # Helper to extract base influencer name
                # "Alex Becker 2" -> "Alex Becker"
                # "Crypto Banter 15 (Gustavo)" -> "Crypto Banter"
                import re
                def get_base_name(name):
                    # Remove trailing numbers, parenthetical notes, and common suffixes
                    base = re.sub(r'\s+\d+(\s*\(.*\))?$', '', name)
                    base = re.sub(r'\s+\(.*\)$', '', base)
                    return base.strip()
                
                # Group by BASE influencer name and count wallets per chain
                influencer_stats = {}
                for wallet in wallets:
                    base_name = get_base_name(wallet.name)
                    chain = wallet.chain
                    
                    if base_name not in influencer_stats:
                        influencer_stats[base_name] = {"EVM": 0, "SOL": 0, "total": 0}
                    
                    influencer_stats[base_name][chain] = influencer_stats[base_name].get(chain, 0) + 1
                    influencer_stats[base_name]["total"] += 1
                
                # Build influencer list
                influencer_list = ""
                total_influencers = len(influencer_stats)
                total_wallets = sum(stats["total"] for stats in influencer_stats.values())
                
                if influencer_stats:
                    # Show top 20, sorted by wallet count
                    sorted_influencers = sorted(influencer_stats.items(), key=lambda x: x[1]["total"], reverse=True)
                    display_count = min(20, len(sorted_influencers))
                    
                    for name, stats in sorted_influencers[:display_count]:
                        evm_count = stats.get("EVM", 0)
                        sol_count = stats.get("SOL", 0)
                        total = stats["total"]
                        
                        # Format: Name (X wallets: Y EVM, Z SOL)
                        chain_breakdown = []
                        if evm_count > 0:
                            chain_breakdown.append(f"{evm_count} EVM")
                        if sol_count > 0:
                            chain_breakdown.append(f"{sol_count} SOL")
                        
                        chain_info = ", ".join(chain_breakdown) if chain_breakdown else "0"
                        influencer_list += f"• *{name}* ({total} wallet{'s' if total != 1 else ''}: {chain_info})\n"
                    
                    # Add "and more" message if there are more influencers
                    if total_influencers > display_count:
                        remaining = total_influencers - display_count
                        influencer_list += f"\n_...and {remaining} more influencer{'s' if remaining != 1 else ''}_"
                else:
                    influencer_list = "• _No influencers currently tracked_\n"
                
            except Exception as e:
                logger.error(f"Error fetching wallet stats: {e}")
                influencer_list = "• _Error loading influencer list_\n"
                total_influencers = 0
                total_wallets = 0

        # Build summary line
        if total_wallets > 0:
            summary_line = f"📊 *Tracking:* {total_influencers} influencers, {total_wallets} wallets\n\n"
        else:
            summary_line = ""

        welcome_text = (
            "🔮 *ALPHA SCANNER*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Tracking *{total_influencers}* influencers ({total_wallets} wallets)\n\n"
            
            "📍 *FIND PLAYS:*\n"
            "/report → What tokens are influencers buying NOW?\n"
            "/cabals → Multiple wallets buying same token = 🚨\n\n"
            
            "🔍 *RESEARCH:*\n"
            "/shill `TOKEN` → Did they buy before tweeting?\n"
            "/profile `NAME` → Is this influencer profitable?\n"
            "/txs `NAME` → What did they trade recently?\n\n"
            
            "📊 *DATA:*\n"
            "/predictions → Who just loaded funds? (about to buy)\n"
            "/alpha → Who has the best win rate?\n"
            "/influencers → Full wallet list\n\n"
            
            "💡 *HOW TO USE:*\n"
            "1. Run `/report` to see what's hot\n"
            "2. If cluster found → Check `/shill TOKEN`\n"
            "3. Influencer bought before tweet = entry signal\n\n"
            
            "_Bot scans every 5 min. Alerts pushed automatically._"
        )
        await message.answer(welcome_text, parse_mode="Markdown")

    async def cmd_status(self, message: types.Message):
        async with AsyncSessionLocal() as session:
            evm_count = await session.execute(select(Wallet).where(Wallet.chain == 'EVM', Wallet.is_active == True))
            sol_count = await session.execute(select(Wallet).where(Wallet.chain == 'SOL', Wallet.is_active == True))
            
            evm_c = len(evm_count.scalars().all())
            sol_c = len(sol_count.scalars().all())
            
            # Get User Status
            user = await session.get(User, message.chat.id)
            plan = user.access_level if user else "UNKNOWN"
            
        await message.answer(f"Status: operational\nPlan: *{plan}*\nTracking:\n- {evm_c} EVM Wallets\n- {sol_c} SOL Wallets", parse_mode="Markdown")

    async def cmd_check(self, message: types.Message):
        # Format: /check <name>
        args = message.text.split()
        if len(args) < 2:
            await message.answer("Usage: /check <name_part>")
            return
        
        query_name = args[1]
        async with AsyncSessionLocal() as session:
            stmt = select(Wallet).where(Wallet.name.ilike(f"%{query_name}%"))
            result = await session.execute(stmt)
            wallets = result.scalars().all()
            
            if not wallets:
                await message.answer("No wallets found.")
                return
            
            # Check Access Level
            user = await session.get(User, message.chat.id)
            access_level = user.access_level if user else "FREE"

            for w in wallets[:5]:
                addr = w.address
                # Researcher gets full address
                if access_level != "RESEARCHER":
                    if len(addr) > 10:
                        addr = f"{addr[:6]}...{addr[-4:]}"
                
                await message.answer(f"Found: {w.name}\nAddr: `{addr}`\nChain: {w.chain}", parse_mode="Markdown")

    async def cmd_upgrade(self, message: types.Message):
        """Show upgrade options and payment instructions."""
        text = (
            "💎 *Upgrade Status* 💎\n\n"
            "Great news! \n"
            "We are currently in a public beta phase.\n\n"
            "✅ *RESEARCHER Access is Enabled for ALL users.*\n"
            "- Live entry/exit alerts\n"
            "- Direct trading links\n"
            "- Full AI Analysis & Sentiment\n"
            "- Full Wallet Addresses\n\n"
            "_No payment is required at this time._"
        )
        await message.answer(text, parse_mode="Markdown")

    async def cmd_verify_payment(self, message: types.Message):
        """Verify payment and upgrade user."""
        args = message.text.split()
        if len(args) < 2:
            await message.answer("Usage: `/verify <tx_hash>`", parse_mode="Markdown")
            return
        
        tx_hash = args[1].strip()
        await message.answer("🔍 *Verifying transaction on Solana blockchain...*\nPlease wait a moment.", parse_mode="Markdown")
        
        # 1. Check strict amounts to guess tier
        # We need to verify against both tiers or see what amount was sent
        # The verification logic checks if amount >= valid_price
        
        # We try Researcher first (higher price)
        success, msg = await payment_verifier.verify_sol_payment(tx_hash, "RESEARCHER")
        new_tier = "RESEARCHER"
        
        if not success:
            # Try Copy Trader
            success, msg_ct = await payment_verifier.verify_sol_payment(tx_hash, "COPY_TRADER")
            if success:
                new_tier = "COPY_TRADER"
                msg = msg_ct
            else:
                # If both fail, return the error from Researcher check (or generic)
                # Usually we want the reason why it failed. 
                pass

        if success:
            # Update User in DB
            async with AsyncSessionLocal() as session:
                user = await session.get(User, message.chat.id)
                if user:
                    user.access_level = new_tier
                    await session.commit()
                    
                    success_text = (
                        f"✅ *Payment Confirmed!*\n\n"
                        f"Your plan has been upgraded to: *{new_tier}*\n"
                        f"{msg}\n\n"
                        "Welcome to the inner circle. 🥂"
                    )
                    await message.answer(success_text, parse_mode="Markdown")
                    logger.info(f"Upgraded user {message.chat.id} to {new_tier} via tx {tx_hash}")
                else:
                    await message.answer("❌ Error: User record not found. Please type /start first.")
        else:
            await message.answer(f"❌ *Verification Failed*\n\nReason: {msg}\n\nPlease check your transaction hash and try again.", parse_mode="Markdown")

    async def cmd_report(self, message: types.Message):
        """Generate actionable intelligence report."""
        await message.answer("📊 *Generating Intelligence Report...*", parse_mode="Markdown")
        
        async with AsyncSessionLocal() as session:
            try:
                from datetime import timedelta
                now = datetime.now(timezone.utc)
                last_24h = now - timedelta(hours=24)
                
                # 1. HOT TOKENS (exclude stablecoins, sorted by unique buyers)
                token_stmt = (
                    select(
                        Transaction.token_symbol,
                        func.count(func.distinct(Transaction.wallet_id)).label('unique_buyers'),
                        func.count().label('total_buys')
                    )
                    .where(Transaction.timestamp >= last_24h)
                    .where(Transaction.tx_type == 'SWAP')
                    .where(Transaction.token_symbol.isnot(None))
                    .where(Transaction.token_symbol.notin_(['USDC', 'USDT', 'SOL', 'ETH', 'WETH', 'WSOL']))
                    .group_by(Transaction.token_symbol)
                    .order_by(desc('unique_buyers'))
                    .limit(8)
                )
                token_result = await session.execute(token_stmt)
                hot_tokens = token_result.all()
                
                # 2. MOST ACTIVE TRADERS (by tx count, not by broken avg)
                trader_stmt = (
                    select(
                        Wallet.name,
                        func.count(Transaction.id).label('tx_count')
                    )
                    .join(Transaction, Transaction.wallet_id == Wallet.id)
                    .where(Transaction.timestamp >= last_24h)
                    .group_by(Wallet.name)
                    .order_by(desc('tx_count'))
                    .limit(5)
                )
                trader_result = await session.execute(trader_stmt)
                active_traders = trader_result.all()
                
                # 3. CLUSTER ALERTS (tokens bought by 2+ wallets in last 6h)
                cluster_cutoff = now - timedelta(hours=6)
                cluster_stmt = (
                    select(
                        Transaction.token_symbol,
                        func.count(func.distinct(Transaction.wallet_id)).label('wallet_count')
                    )
                    .where(Transaction.timestamp >= cluster_cutoff)
                    .where(Transaction.tx_type == 'SWAP')
                    .where(Transaction.token_symbol.isnot(None))
                    .where(Transaction.token_symbol.notin_(['USDC', 'USDT', 'SOL', 'ETH', 'WETH', 'WSOL']))
                    .group_by(Transaction.token_symbol)
                    .having(func.count(func.distinct(Transaction.wallet_id)) >= 2)
                    .order_by(desc('wallet_count'))
                    .limit(3)
                )
                cluster_result = await session.execute(cluster_stmt)
                clusters = cluster_result.all()
                
                # Build Report
                report = "📈 *INTELLIGENCE REPORT (24h)*\n\n"
                
                # Clusters Section - with TX links
                if clusters:
                    report += "🎯 *CLUSTER ACTIVITY (6h):*\n"
                    for symbol, wallet_count in clusters:
                        # Get buyer names + tx hashes
                        buyer_stmt = (
                            select(Wallet.name, Transaction.tx_hash, Wallet.chain)
                            .join(Transaction, Transaction.wallet_id == Wallet.id)
                            .where(Transaction.token_symbol == symbol)
                            .where(Transaction.timestamp >= cluster_cutoff)
                            .distinct()
                            .limit(4)
                        )
                        buyer_result = await session.execute(buyer_stmt)
                        buyers = buyer_result.all()
                        
                        report += f"• *${symbol}* ({wallet_count} buyers)\n"
                        for name, tx_hash, chain in buyers[:3]:
                            short_name = name[:12] + ".." if len(name) > 12 else name
                            if chain == 'SOL':
                                link = f"https://solscan.io/tx/{tx_hash}"
                            else:
                                link = f"https://basescan.org/tx/{tx_hash}"
                            report += f"  └ {short_name} [TX]({link})\n"
                        if len(buyers) > 3:
                            report += f"  └ +{wallet_count-3} more\n"
                    report += "\n"
                else:
                    report += "⏳ *No cluster activity yet.*\n"
                    report += "_Waiting for multiple influencers to buy the same token._\n\n"
                
                # Hot Tokens with buyers
                if hot_tokens:
                    report += "🔥 *HOT TOKENS:*\n"
                    for symbol, unique_buyers, total_buys in hot_tokens[:5]:
                        # Get buyer names
                        buyer_stmt = (
                            select(Wallet.name)
                            .join(Transaction, Transaction.wallet_id == Wallet.id)
                            .where(Transaction.token_symbol == symbol)
                            .where(Transaction.timestamp >= last_24h)
                            .distinct()
                            .limit(3)
                        )
                        buyer_result = await session.execute(buyer_stmt)
                        buyer_names = [b[0][:10] for b in buyer_result.all()]
                        
                        buyers_str = ", ".join(buyer_names)
                        if unique_buyers > 3:
                            buyers_str += f" +{unique_buyers-3}"
                        
                        report += f"• ${symbol}: {buyers_str}\n"
                    report += "\n"
                
                report += "_Use `/shill <token>` to dig deeper._"
                
                await message.answer(report, parse_mode="Markdown", disable_web_page_preview=True)
                
            except Exception as e:
                logger.error(f"Report error: {e}")
                await message.answer(f"❌ Error: {e}")

    async def cmd_influencers(self, message: types.Message):
        """List all tracked influencers grouped by base name."""
        import re
        
        def get_base_name(name):
            base = re.sub(r'\s+\d+(\s*\(.*\))?$', '', name)
            base = re.sub(r'\s+\(.*\)$', '', base)
            return base.strip()
        
        async with AsyncSessionLocal() as session:
            try:
                # Get all wallets with stats
                stmt = (
                    select(Wallet.name, Wallet.chain, WalletStats.total_tx_count)
                    .outerjoin(WalletStats, Wallet.id == WalletStats.wallet_id)
                    .where(Wallet.is_active == True)
                )
                result = await session.execute(stmt)
                wallets = result.all()
                
                if not wallets:
                    await message.answer("No influencers tracked yet.")
                    return
                
                # Group by base name
                influencer_data = {}
                for name, chain, tx_count in wallets:
                    base = get_base_name(name)
                    if base not in influencer_data:
                        influencer_data[base] = {"wallets": 0, "evm": 0, "sol": 0, "txs": 0}
                    influencer_data[base]["wallets"] += 1
                    influencer_data[base][chain.lower() if chain else "evm"] += 1
                    influencer_data[base]["txs"] += tx_count or 0
                
                # Sort by tx count
                sorted_influencers = sorted(
                    influencer_data.items(), 
                    key=lambda x: x[1]["txs"], 
                    reverse=True
                )[:25]  # Top 25
                
                text = "👥 *TOP INFLUENCERS*\n"
                text += f"_Tracking {len(influencer_data)} influencers_\n\n"
                
                for name, data in sorted_influencers:
                    short_name = name[:22] + "..." if len(name) > 22 else name
                    chains = []
                    if data["evm"] > 0:
                        chains.append(f"{data['evm']} EVM")
                    if data["sol"] > 0:
                        chains.append(f"{data['sol']} SOL")
                    chain_str = ", ".join(chains) if chains else "?"
                    
                    text += f"• *{short_name}*\n"
                    text += f"  {data['wallets']} wallets ({chain_str}) | {data['txs']} txs\n"
                
                text += "\n_Use `/profile <name>` for details_"
                
                await message.answer(text, parse_mode="Markdown")
                
            except Exception as e:
                logger.error(f"Influencers cmd error: {e}")
                await message.answer(f"❌ Error: {e}")

    async def cmd_txs(self, message: types.Message):
        """Show recent transactions for a specific influencer."""
        args = message.text.split(maxsplit=1)
        
        if len(args) < 2:
            await message.answer(
                "📋 *Transaction History*\n\n"
                "Usage: `/txs <influencer name>`\n\n"
                "Example: `/txs Murad`\n\n"
                "Use `/influencers` to see available names.",
                parse_mode="Markdown"
            )
            return
        
        search_name = args[1].strip().lower()
        
        async with AsyncSessionLocal() as session:
            try:
                # Find matching wallet
                stmt = select(Wallet).where(
                    Wallet.name.ilike(f"%{search_name}%"),
                    Wallet.is_active == True
                ).limit(1)
                result = await session.execute(stmt)
                wallet = result.scalar_one_or_none()
                
                if not wallet:
                    await message.answer(f"❌ No influencer found matching '{search_name}'")
                    return
                
                # Get recent transactions
                tx_stmt = (
                    select(Transaction)
                    .where(Transaction.wallet_id == wallet.id)
                    .order_by(desc(Transaction.id))
                    .limit(15)
                )
                tx_result = await session.execute(tx_stmt)
                txs = tx_result.scalars().all()
                
                text = f"📜 *{wallet.name}*\n"
                text += f"Recent Transactions:\n\n"
                
                if not txs:
                    text += "_No transactions recorded yet._"
                else:
                    for tx in txs:
                        symbol = tx.token_symbol or "SOL"
                        amount = tx.amount or 0
                        tx_type = tx.tx_type or "?"
                        
                        emoji = "🔄" if tx_type == "SWAP" else "📤" if tx_type == "TRANSFER" else "❓"
                        
                        # Short hash link
                        short_hash = tx.tx_hash[:8] + "..."
                        link = f"https://solscan.io/tx/{tx.tx_hash}"
                        
                        text += f"{emoji} *{tx_type}* | {amount:.2f} {symbol}\n"
                        text += f"   [View]({link})\n"
                
                await message.answer(text, parse_mode="Markdown", disable_web_page_preview=True)
                
            except Exception as e:
                logger.error(f"Txs cmd error: {e}")
                await message.answer(f"❌ Error: {e}")

    async def cmd_insights(self, message: types.Message):
        """Show recent high-value moments, now with TOKEN SYMBOLS."""
        async with AsyncSessionLocal() as session:
            try:
                # Top 10 recent moments + Token Symbol (Joined via Transaction)
                stmt = (
                    select(Moment, Wallet.name, Transaction.token_symbol)
                    .join(Wallet, Moment.wallet_id == Wallet.id)
                    .outerjoin(Transaction, Moment.tx_hash == Transaction.tx_hash)
                    .order_by(desc(Moment.detected_at))
                    .limit(40) # Fetch more to dedupe
                )
                
                result = await session.execute(stmt)
                moments = result.all()
                
                text = "🔮 *LATEST INSIGHTS*\n\n"
                
                if not moments:
                    text += "_System is learning patterns..._\n"
                    text += "Wait for new trades."
                else:
                    seen_moments = set()
                    displayed_count = 0
                    
                    for m, wallet_name, token_symbol in moments:
                        # Deduplication Key: Wallet + Type + Token (if avail)
                        token_str = token_symbol if token_symbol else "UNKNOWN"
                        key = (wallet_name, m.moment_type, token_str)
                        
                        if key in seen_moments:
                            continue
                        seen_moments.add(key)
                        
                        emoji = {"NEW_TOKEN": "🆕", "WHALE_MOVE": "🐋", "ACCUMULATION": "🔄", "ABOVE_AVG": "📈", "CABAL": "📍"}.get(m.moment_type, "⚡")
                        
                        name = wallet_name[:15] + "..." if len(wallet_name) > 15 else wallet_name
                        
                        # ACTIONABLE FORMAT: "🆕 NEW_TOKEN $WIF | WalletName"
                        token_display = f"*{token_symbol}*" if token_symbol else ""
                        
                        # Clean description
                        raw_desc = m.description.replace("**", "").replace("\n", " ")
                        
                        text += f"{emoji} *{m.moment_type}*"
                        if token_display:
                            text += f" on {token_display}"
                        text += f" | {name}\n"
                        
                        # Only show description if it adds value (not just repeating title)
                        if "New Token Alert" not in raw_desc and "Whale Move Detected" not in raw_desc:
                             text += f"   _{raw_desc[:60]}..._\n\n"
                        else:
                             text += "\n"
                        
                        displayed_count += 1
                        if displayed_count >= 8:
                            break
                
                text += "\n_Signals based on real-time moves._"
                await message.answer(text, parse_mode="Markdown")

            except Exception as e:
                logger.error(f"Insights error: {e}")
                await message.answer(f"❌ Error: {e}")

    async def cmd_predictions(self, message: types.Message):
        """Show active reload predictions - who is about to buy?"""
        from datetime import datetime, timedelta, timezone
        
        async with AsyncSessionLocal() as session:
            try:
                # Get active (unresolved) reloads from last 2 hours
                now = datetime.now(timezone.utc)
                cutoff = now - timedelta(minutes=120)
                
                stmt = (
                    select(
                        ReloadEvent,
                        Wallet.name,
                        WalletStats.reload_buy_probability,
                        WalletStats.avg_time_to_buy_after_reload,
                        WalletStats.avg_buy_sol,
                        WalletStats.max_buy_sol
                    )
                    .join(Wallet, ReloadEvent.wallet_id == Wallet.id)
                    .outerjoin(WalletStats, Wallet.id == WalletStats.wallet_id)
                    .where(ReloadEvent.followed_by_buy == None)
                    .order_by(desc(ReloadEvent.detected_at))
                    .limit(15)
                )
                
                result = await session.execute(stmt)
                predictions = result.all()
                
                text = "🔮 *ACTIVE PREDICTIONS*\n\n"
                
                if not predictions:
                    text += "_No active predictions right now._\n\n"
                    text += "Waiting for influencers to receive SOL..."
                else:
                    # Group predictions by wallet
                    grouped_preds = {}
                    for reload, wallet_name, prob, avg_time, avg_buy, max_buy in predictions:
                        if wallet_name not in grouped_preds:
                            grouped_preds[wallet_name] = {
                                "total_amount": 0.0,
                                "count": 0,
                                "prob": prob,
                                "avg_time": avg_time,
                                "avg_buy": avg_buy,
                                "max_buy": max_buy,
                                "latest_reload": reload.detected_at
                            }
                        grouped_preds[wallet_name]["total_amount"] += reload.amount
                        grouped_preds[wallet_name]["count"] += 1
                        # Keep latest timestamp
                        if reload.detected_at > grouped_preds[wallet_name]["latest_reload"]:
                            grouped_preds[wallet_name]["latest_reload"] = reload.detected_at

                    for wallet_name, data in grouped_preds.items():
                        name = wallet_name[:22] + "..." if len(wallet_name) > 22 else wallet_name
                        
                        # Calculate time since LATEST reload
                        detected = data["latest_reload"]
                        if detected.tzinfo is None:
                            detected = detected.replace(tzinfo=timezone.utc)
                        minutes_ago = int((now - detected).total_seconds() / 60)
                        
                        text += f"⚡ *{name}*\n"
                        
                        # Formatting: "Received 50 SOL (3 txs) - 5m ago"
                        amount_str = f"{data['total_amount']:.1f}"
                        count_part = f" ({data['count']} txs)" if data['count'] > 1 else ""
                        
                        text += f"   💰 Loaded *{amount_str} SOL*{count_part} • {minutes_ago}m ago\n"
                        
                        # Simplified context - only probability
                        if data['prob'] and data['avg_time']:
                            text += f"   🎯 {data['prob']:.0f}% chance of buy within {data['avg_time']} min\n"
                        
                        text += "\n"
                
                text += "_Only active reloads shown._"
                
                await message.answer(text, parse_mode="Markdown")
                
            except Exception as e:
                logger.error(f"Predictions cmd error: {e}")
                await message.answer(f"❌ Error: {e}")

    async def cmd_cabals(self, message: types.Message):
        """Show detected cabal activity - coordinated wallet clusters."""
        from datetime import datetime, timedelta
        
        async with AsyncSessionLocal() as session:
            try:
                from datetime import timezone
                now = datetime.now(timezone.utc)
                
                # Get cabal moments from last 24 hours  
                stmt = (
                    select(Moment, Wallet.name)
                    .join(Wallet, Moment.wallet_id == Wallet.id)
                    .where(Moment.moment_type == "CABAL")
                    .order_by(desc(Moment.detected_at))
                    .limit(10)
                )
                
                result = await session.execute(stmt)
                cabals = result.all()
                
                text = "🕸️ *CABAL DETECTIONS (24h)*\n\n"
                
                if not cabals:
                    text += "_No coordinated activity detected yet._\n\n"
                    text += "Cabals are detected when 2+ tracked wallets\n"
                    text += "buy the same token within 30 minutes."
                else:
                    seen_cabals = set()
                    
                    for moment, wallet_name in cabals:
                        # Description contains "Token: $XXX\nCluster: Y wallets..."
                        # De-dupe by token and approximate time (ignore duplicate wallet alerts)
                        # We parse the Token ticker from description
                        try:
                            token_ticker = moment.description.split('\n')[0].split(': ')[1]
                        except:
                            token_ticker = "UNKNOWN"
                            
                        key = (token_ticker, moment.description)
                        if key in seen_cabals:
                            continue
                        seen_cabals.add(key)
                        
                        # Parse description for display
                        # Clean up formatting
                        if moment.description:
                            desc = moment.description.replace("Token:", "🎯 token:").replace("Cluster:", "👥 cluster:")
                        else:
                            desc = "Unknown Cluster Activity"
                            
                        text += f"*{desc}*\n"
                        
                        # Time ago (handle timezone)
                        detected = moment.detected_at
                        if detected.tzinfo is None:
                            detected = detected.replace(tzinfo=timezone.utc)
                        time_ago = now - detected
                        hours = int(time_ago.total_seconds() / 3600)
                        mins = int((time_ago.total_seconds() % 3600) / 60)
                        text += f"_Detected {hours}h {mins}m ago_\n\n"
                        
                        if len(seen_cabals) >= 5:
                            break
                
                text += "\n_High confidence = shared funding sources._"
                
                await message.answer(text, parse_mode="Markdown")
                
            except Exception as e:
                logger.error(f"Cabals cmd error: {e}")
                await message.answer(f"❌ Error: {e}")

    async def cmd_profile(self, message: types.Message):
        """Show detailed trading profile/fingerprint for an influencer."""
        from src.analysis.fingerprint_analyzer import FingerprintAnalyzer
        
        args = message.text.split(maxsplit=1)
        
        if len(args) < 2:
            await message.answer(
                "🎭 *Trading Fingerprint*\n\n"
                "Usage: `/profile <influencer name>`\n\n"
                "Example: `/profile Murad`\n\n"
                "Shows: Win Rate, Trading Style, Hold Time",
                parse_mode="Markdown"
            )
            return
        
        search_name = args[1].strip().lower()
        analyzer = FingerprintAnalyzer()
        
        async with AsyncSessionLocal() as session:
            try:
                # Find matching wallet
                stmt = select(Wallet).where(
                    Wallet.name.ilike(f"%{search_name}%"),
                    Wallet.is_active == True
                ).limit(1)
                result = await session.execute(stmt)
                wallet = result.scalar_one_or_none()
                
                if not wallet:
                    await message.answer(f"❌ No influencer found matching '{search_name}'")
                    return
                
                await message.answer(f"🔍 Analyzing {wallet.name}...", parse_mode="Markdown")
                
                # Get or calculate profile
                profile = await analyzer.get_profile(session, wallet.id)
                
                if not profile:
                    await message.answer("_Not enough trading data yet._", parse_mode="Markdown")
                    return
                
                # Get basic stats too
                stats_stmt = select(WalletStats).where(WalletStats.wallet_id == wallet.id)
                stats_result = await session.execute(stats_stmt)
                stats = stats_result.scalar_one_or_none()
                
                # Build profile display
                style_emoji = {"SNIPER": "🎯", "TRADER": "📊", "HOLDER": "💎"}.get(profile.get("style"), "❓")
                
                text = f"🎭 *{wallet.name}*\n"
                text += f"━━━━━━━━━━━━━━━\n\n"
                
                # Win Rate
                win_rate = profile.get("win_rate")
                if win_rate is not None:
                    wr_emoji = "🟢" if win_rate >= 60 else "🟡" if win_rate >= 40 else "🔴"
                    text += f"{wr_emoji} *Win Rate:* {win_rate:.0f}%\n"
                else:
                    text += f"❓ *Win Rate:* Calculating...\n"
                
                # Style
                text += f"{style_emoji} *Style:* {profile.get('style', 'Unknown')}\n"
                
                # Hold Time
                hold = profile.get("avg_hold_hours")
                if hold:
                    if hold < 24:
                        hold_str = f"{hold:.1f} hours"
                    else:
                        hold_str = f"{hold/24:.1f} days"
                    text += f"⏱️ *Avg Hold:* {hold_str}\n"
                
                # Alpha Score
                alpha = profile.get("alpha_score", 100)
                alpha_emoji = "🔥" if alpha >= 80 else "⚠️" if alpha >= 50 else "❄️"
                text += f"{alpha_emoji} *Alpha Score:* {alpha:.0f}/100\n"
                
                # Trades Analyzed
                text += f"\n📈 _Based on {profile.get('trades_analyzed', 0)} trades_"
                
                await message.answer(text, parse_mode="Markdown")
                
            except Exception as e:
                logger.error(f"Profile cmd error: {e}")
                await message.answer(f"❌ Error: {e}")

    async def cmd_alpha(self, message: types.Message):
        """Show alpha leaderboard - who has the freshest edge?"""
        # Rewrite to ignore wallets with no trades
        async with AsyncSessionLocal() as session:
            try:
                # Get top alpha wallets BUT ONLY if they have > 0 trades or copiers recorded
                # This prevents "100 Alpha" for inactive wallets
                stmt = (
                    select(Wallet.name, WalletStats.alpha_score, WalletStats.avg_copiers_per_trade, WalletStats.win_rate)
                    .join(WalletStats, Wallet.id == WalletStats.wallet_id)
                    .where(WalletStats.alpha_score.isnot(None))
                    .where(WalletStats.trades_analyzed > 0) # CRITICAL FILTER
                    .order_by(desc(WalletStats.alpha_score))
                    .limit(10)
                )
                
                result = await session.execute(stmt)
                leaders = result.all()
                
                text = "🔥 *ALPHA LEADERBOARD*\n"
                text += "_Highest = Least crowded edge_\n\n"
                
                if not leaders:
                    text += "_No proven alpha yet. Wait for closed trades._\n"
                    text += "_(Leaderboard requires at least 1 analyzed trade)_\n"
                else:
                    for i, (name, alpha, copiers, win_rate) in enumerate(leaders, 1):
                        short_name = name[:18] + "..." if len(name) > 18 else name
                        
                        # Alpha emoji
                        if alpha >= 80: emoji = "🔥"
                        elif alpha >= 60: emoji = "✅"
                        elif alpha >= 40: emoji = "⚠️"
                        else: emoji = "❄️"
                        
                        copier_text = f"{copiers:.1f}" if copiers else "0"
                        win_text = f"{win_rate*100:.0f}%" if win_rate is not None else "??"
                        
                        text += f"{i}. {emoji} *{short_name}*\n"
                        text += f"   Alpha: {alpha:.0f} | Copiers: {copier_text} | Win: {win_text}\n"
                
                text += "\n_Lower copiers = fresher alpha_"
                
                await message.answer(text, parse_mode="Markdown")
                
            except Exception as e:
                logger.error(f"Alpha cmd error: {e}")
                await message.answer(f"❌ Error: {e}")

    async def cmd_shill(self, message: types.Message):
        """Check for pre-shill accumulation and Twitter hype."""
        from src.analysis.shill_detector import ShillDetector
        from src.analysis.twitter_monitor import TwitterMonitor
        
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.answer(
                "🚨 *NARRATIVE CHECK*\n\n"
                "Usage: `/shill <token_symbol_or_address>`\n\n"
                "Example: `/shill WIF`\n"
                "_Checks on-chain buys + Twitter narrative._"
            , parse_mode="Markdown")
            return
            
        token_input = args[1]
        await message.answer(f"🕵️‍♂️ Analyzing *{token_input}* (Chain + Twitter)...")
        
        async with AsyncSessionLocal() as session:
            try:
                # 1. On-Chain Analysis
                detector = ShillDetector()
                analysis = await detector.check_token_history(session, token_input)
                
                # 2. Twitter Analysis
                monitor = TwitterMonitor()
                tweets = monitor.search_tweets(token_input)
                
                report = "⚠️ *NARRATIVE REPORT*\n\n"
                
                # --- On-Chain Section ---
                if not analysis:
                    report += f"✅ *On-Chain:* No tracked influencers holding.\n"
                else:
                    verdict = detector.get_shill_verdict(analysis)
                    report += f"🚨 *PRE-SHILL DETECTED*\n"
                    report += f"Buyers: *{verdict['buyer_count']}* influencers\n"
                    report += f"First Buy: *{verdict['days_ago']}d {verdict['hours_ago']}h ago*\n"
                    
                    report += "\n📜 *Timeline:*\n"
                    for buyer in analysis['buyers'][:5]:
                        t_str = buyer['time'].strftime("%d %b %H:%M")
                        report += f"• {buyer['wallet']}: {buyer['amount']:.1f} @ {t_str}\n"

                # --- Twitter Section ---
                report += "\n🐦 *Twitter Scanner:*\n"
                if tweets and "data" in tweets:
                    report += f"Found *{len(tweets['data'])}* recent tweets.\n"
                    # Simple check if any come from linked handles (would need DB query here, skipping for speed)
                    # Just show recent 2
                    for t in tweets['data'][:2]:
                        text_clean = t['text'].replace('\n', ' ')[:50] + "..."
                        report += f"• `{text_clean}`\n"
                elif tweets and "error" in tweets:
                    report += "⚠️ Twitter Rate Limit or Error.\n"
                else:
                    report += "❌ No recent tweets found (or API error).\n"
                    
                await message.answer(report, parse_mode="Markdown")
                
            except Exception as e:
                logger.error(f"Shill cmd error: {e}")
                await message.answer(f"❌ Error: {e}")

    async def broadcast_alert(self, wallet_name, tx_hash, chain, analysis=None, importance="MEDIUM"):
        """
        Broadcasts alerts to all users based on their subscription tier.
        
        Args:
            wallet_name: Name of the wallet
            tx_hash: Transaction hash
            chain: Chain (SOL or EVM)
            analysis: AI-generated or filtered analysis
            importance: Transaction importance level (SKIP, LOW, MEDIUM, HIGH)
        """
        if not self.bot:
            return

        # Importance emojis
        importance_icons = {
            "SKIP": "⏭️",
            "LOW": "📊",
            "MEDIUM": "⚡",
            "HIGH": "🔥"
        }
        
        importance_icon = importance_icons.get(importance, "📍")

        async with AsyncSessionLocal() as session:
            stmt = select(User)
            result = await session.execute(stmt)
            users = result.scalars().all()

            for user in users:
                try:
                    msg = ""
                    # 1. FREE MODE
                    if user.access_level == "FREE":
                        # Only notify for MEDIUM and HIGH
                        if importance in ["MEDIUM", "HIGH"]:
                            msg = (
                                f"{importance_icon} *ACTION DETECTED* {importance_icon}\n\n"
                                f"Influencer: *{wallet_name}*\n"
                                f"Chain: *{chain}*\n"
                                f"Priority: *{importance}*\n\n"
                                f"_Upgrade to Copy Trader or Researcher to see transaction details._"
                            )
                    
                    # 2. COPY TRADER MODE
                    elif user.access_level == "COPY_TRADER":
                        link = ""
                        if chain == "SOL":
                            link = f"https://solscan.io/tx/{tx_hash}"
                            # Simulated Trojan Link (needs token address usually, using hash as placeholder for MVP)
                            trade_link = f"[Snipe on Trojan](https://t.me/solana_trojan_bot?start={tx_hash})" 
                        else:
                            link = f"https://etherscan.io/tx/{tx_hash}"
                            trade_link = f"[Snipe on Maestro](https://t.me/maestro?start={tx_hash})"

                        header = "🚀 *TRADE ALERT* 🚀" if importance == "HIGH" else "⚡ *Trade Signal* ⚡"
                        msg = (
                            f"{header}\n\n"
                            f"Influencer: *{wallet_name}*\n"
                            f"Chain: *{chain}*\n"
                            f"Priority: {importance_icon} *{importance}*\n"
                            f"Tx: `{tx_hash[:16]}...`\n\n"
                            f"[View on Explorer]({link})\n{trade_link}"
                        )

                    # 3. RESEARCHER MODE
                    elif user.access_level == "RESEARCHER":
                        link = f"https://solscan.io/tx/{tx_hash}" if chain == "SOL" else f"https://etherscan.io/tx/{tx_hash}"
                        ai_text = analysis if analysis else "No specific anomaly detected."
                        
                        # Enhanced header based on importance
                        if importance == "HIGH":
                            header = "🔥 *CRITICAL MOVE DETECTED* 🔥"
                        elif importance == "MEDIUM":
                            header = "🔬 *DEEP DIVE* 🔬"
                        else:
                            header = "📊 *Activity Logged* 📊"
                        
                        msg = (
                            f"{header}\n\n"
                            f"Influencer: *{wallet_name}*\n"
                            f"Chain: *{chain}*\n"
                            f"Priority: {importance_icon} *{importance}*\n"
                            f"Tx: `{tx_hash}`\n\n"
                            f"🧠 *Analysis:*\n{ai_text}\n\n"
                            f"[View on Explorer]({link})"
                        )
                    
                    # Send
                    if msg:
                        await self.bot.send_message(user.chat_id, msg, parse_mode="Markdown")

                except Exception as e:
                    logger.error(f"Failed to send alert to {user.chat_id}: {e}")

    
    # Legacy wrapper
    async def send_alert(self, text):
         if self.bot and self.admin_chat_id:
             try:
                 await self.bot.send_message(self.admin_chat_id, text, parse_mode="Markdown")
             except Exception as e:
                pass

bot_instance = TelegramBot()
