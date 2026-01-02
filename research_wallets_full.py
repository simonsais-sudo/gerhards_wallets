"""
Enhanced On-Chain Wallet Research with Visualization
Analyzes ALL wallets and creates visual insights
"""

import asyncio
import json
import os
from datetime import datetime, timedelta
from collections import defaultdict
import aiohttp
from dotenv import load_dotenv
# import matplotlib.pyplot as plt
# import matplotlib.dates as mdates
from collections import Counter

load_dotenv()

HELIUS_API_KEY = "a6b6d793-f3d4-4d02-bc36-0a758ac735cf"

# Stats collectors
stats = {
    "total_wallets": 0,
    "active_wallets": 0,
    "inactive_wallets": 0,
    "total_transactions": 0,
    "buy_signals": [],
    "sell_signals": [],
    "token_activity": defaultdict(int),
    "wallet_activity": {},
    "errors": [],
    "daily_activity": defaultdict(int),
    "influencer_activity": defaultdict(lambda: {"buys": 0, "sells": 0, "total_volume": 0})
}

async def fetch_solana_transactions(session, address: str, limit: int = 20):
    """Fetch recent transactions for a Solana wallet using Helius"""
    url = f"https://api.helius.xyz/v0/addresses/{address}/transactions?api-key={HELIUS_API_KEY}&limit={limit}"
    
    try:
        async with session.get(url, timeout=10) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                return None
    except Exception as e:
        stats["errors"].append(f"{address[:8]}...: {str(e)}")
        return None

async def analyze_solana_wallet(session, wallet: dict):
    """Analyze a single Solana wallet"""
    address = wallet["address"]
    name = wallet["name"]
    
    txs = await fetch_solana_transactions(session, address, limit=20)
    
    if txs is None or len(txs) == 0:
        print(f"DEBUG: Wallet {name} ({address[:8]}) is inactive or failed.")
        stats["inactive_wallets"] += 1
        return None
    
    print(f"DEBUG: Wallet {name} ({address[:8]}) found {len(txs)} txs.")
    
    stats["active_wallets"] += 1
    stats["total_transactions"] += len(txs)
    
    # Extract base influencer name
    base_name = name.split(" ")[0] + " " + (name.split(" ")[1] if len(name.split(" ")) > 1 else "")
    if base_name.endswith(" ("):
        base_name = name.split(" ")[0]
    
    # Analyze transactions
    for tx in txs:
        tx_type = tx.get("type", "UNKNOWN")
        timestamp = tx.get("timestamp")
        
        # Track daily activity
        if timestamp:
            date = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")
            stats["daily_activity"][date] += 1
        
        # Look for swaps
        if tx_type == "SWAP":
            description = tx.get("description", "")
            
            # Track influencer activity
            stats["influencer_activity"][base_name]["total_volume"] += 1
            
            # Token tracking
            token_transfers = tx.get("tokenTransfers", [])
            for transfer in token_transfers:
                token_mint = transfer.get("mint", "Unknown")
                stats["token_activity"][token_mint] += 1
            
            # Classify buy/sell
            if "to SOL" in description.lower() or "to USDC" in description.lower():
                stats["sell_signals"].append({"wallet": name, "tx": description[:80], "date": date if timestamp else "Unknown"})
                stats["influencer_activity"][base_name]["sells"] += 1
            else:
                stats["buy_signals"].append({"wallet": name, "tx": description[:80], "date": date if timestamp else "Unknown"})
                stats["influencer_activity"][base_name]["buys"] += 1
    
    return True

async def research_all_wallets():
    """Research ALL Solana wallets"""
    
    # Load wallets
    with open("config/wallets.json", "r") as f:
        all_wallets = json.load(f)
    
    sol_wallets = [w for w in all_wallets if w.get("chain") == "SOL"]
    
    print("=" * 70)
    print("🔍 COMPREHENSIVE ON-CHAIN WALLET RESEARCH")
    print("=" * 70)
    print(f"\n📊 Total Solana Wallets: {len(sol_wallets)}")
    print(f"🔎 Analyzing ALL wallets (this will take ~2-3 minutes)...\n")
    
    stats["total_wallets"] = len(sol_wallets)
    
    async with aiohttp.ClientSession() as session:
        for i, wallet in enumerate(sol_wallets):
            print(f"   [{i+1}/{len(sol_wallets)}] {wallet['name'][:50]:<50}", end="\r")
            await analyze_solana_wallet(session, wallet)
            await asyncio.sleep(0.2)  # Rate limit
        
        print("\n")
    
    # Generate visualizations
    # create_visualizations()
    
    # Print summary
    print_summary()
    
    # Save results
    save_results()

def create_visualizations():
    """Create visual analytics"""
    print("\n📊 Generating visualizations...")
    
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle('Influencer Wallet On-Chain Activity Analysis', fontsize=16, fontweight='bold')
    
    # 1. Daily Activity Timeline
    if stats["daily_activity"]:
        dates = sorted(stats["daily_activity"].keys())[-30:]  # Last 30 days
        counts = [stats["daily_activity"][d] for d in dates]
        
        ax1.plot(dates, counts, marker='o', linewidth=2, markersize=6, color='#2ecc71')
        ax1.fill_between(range(len(dates)), counts, alpha=0.3, color='#2ecc71')
        ax1.set_title('Daily Transaction Activity (Last 30 Days)', fontweight='bold')
        ax1.set_xlabel('Date')
        ax1.set_ylabel('Number of Transactions')
        ax1.grid(True, alpha=0.3)
        ax1.tick_params(axis='x', rotation=45)
        
        # Reduce x-axis labels
        if len(dates) > 10:
            step = len(dates) // 10
            ax1.set_xticks(range(0, len(dates), step))
            ax1.set_xticklabels([dates[i] for i in range(0, len(dates), step)])
    
    # 2. Top Influencers by Activity
    top_influencers = sorted(
        stats["influencer_activity"].items(), 
        key=lambda x: x[1]["total_volume"], 
        reverse=True
    )[:15]
    
    names = [name[:20] for name, _ in top_influencers]
    volumes = [data["total_volume"] for _, data in top_influencers]
    
    bars = ax2.barh(names, volumes, color='#3498db')
    ax2.set_title('Top 15 Most Active Influencers', fontweight='bold')
    ax2.set_xlabel('Number of Swaps')
    ax2.invert_yaxis()
    
    # Add value labels
    for i, (bar, vol) in enumerate(zip(bars, volumes)):
        ax2.text(vol, i, f' {vol}', va='center', fontweight='bold')
    
    # 3. Buy vs Sell Signals
    buy_count = len(stats["buy_signals"])
    sell_count = len(stats["sell_signals"])
    
    colors = ['#2ecc71', '#e74c3c']
    sizes = [buy_count, sell_count]
    labels = [f'Buy Signals\n({buy_count})', f'Sell Signals\n({sell_count})']
    
    wedges, texts, autotexts = ax3.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%',
                                         startangle=90, textprops={'fontweight': 'bold'})
    ax3.set_title('Buy vs Sell Signal Distribution', fontweight='bold')
    
    # 4. Most Traded Tokens
    if stats["token_activity"]:
        top_tokens = sorted(stats["token_activity"].items(), key=lambda x: x[1], reverse=True)[:10]
        token_names = [f"Token {i+1}" for i in range(len(top_tokens))]  # Anonymous
        token_counts = [count for _, count in top_tokens]
        
        bars = ax4.bar(token_names, token_counts, color='#9b59b6')
        ax4.set_title('Top 10 Most Traded Tokens', fontweight='bold')
        ax4.set_xlabel('Token')
        ax4.set_ylabel('Trade Count')
        ax4.tick_params(axis='x', rotation=45)
        
        # Add value labels
        for bar, count in zip(bars, token_counts):
            height = bar.get_height()
            ax4.text(bar.get_x() + bar.get_width()/2., height,
                    f'{int(count)}', ha='center', va='bottom', fontweight='bold')
    
    plt.tight_layout()
    plt.savefig('wallet_analysis.png', dpi=300, bbox_inches='tight')
    print("   ✅ Saved: wallet_analysis.png")
    
    # Additional: Influencer Sentiment Chart
    fig2, ax = plt.subplots(figsize=(14, 8))
    
    top_influencers_sentiment = sorted(
        [(name, data["buys"], data["sells"]) 
         for name, data in stats["influencer_activity"].items() 
         if data["total_volume"] > 0],
        key=lambda x: x[1] + x[2],
        reverse=True
    )[:20]
    
    names = [name[:25] for name, _, _ in top_influencers_sentiment]
    buys = [b for _, b, _ in top_influencers_sentiment]
    sells = [s for _, _, s in top_influencers_sentiment]
    
    x = range(len(names))
    width = 0.35
    
    ax.barh([i - width/2 for i in x], buys, width, label='Buys', color='#2ecc71')
    ax.barh([i + width/2 for i in x], sells, width, label='Sells', color='#e74c3c')
    
    ax.set_yticks(x)
    ax.set_yticklabels(names)
    ax.set_xlabel('Number of Transactions', fontweight='bold')
    ax.set_title('Influencer Trading Sentiment (Buy vs Sell)', fontsize=14, fontweight='bold')
    ax.legend()
    ax.invert_yaxis()
    ax.grid(axis='x', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('influencer_sentiment.png', dpi=300, bbox_inches='tight')
    print("   ✅ Saved: influencer_sentiment.png")

def print_summary():
    """Print comprehensive summary"""
    print("\n" + "=" * 70)
    print("📈 COMPREHENSIVE RESEARCH RESULTS")
    print("=" * 70)
    
    print(f"\n📊 Overall Statistics:")
    print(f"   • Wallets Analyzed: {stats['total_wallets']}")
    print(f"   • Active Wallets: {stats['active_wallets']} ({stats['active_wallets']/stats['total_wallets']*100:.1f}%)")
    print(f"   • Inactive Wallets: {stats['inactive_wallets']}")
    print(f"   • Total Transactions: {stats['total_transactions']}")
    
    print(f"\n🔥 Trading Signals:")
    print(f"   • Buy Signals: {len(stats['buy_signals'])}")
    print(f"   • Sell Signals: {len(stats['sell_signals'])}")
    
    if len(stats['buy_signals']) > 0 or len(stats['sell_signals']) > 0:
        total_signals = len(stats['buy_signals']) + len(stats['sell_signals'])
        buy_ratio = len(stats['buy_signals']) / total_signals * 100
        print(f"   • Buy/Sell Ratio: {buy_ratio:.1f}% / {100-buy_ratio:.1f}%")
    
    # Market sentiment
    if len(stats['buy_signals']) > len(stats['sell_signals']) * 1.5:
        sentiment = "🟢 BULLISH (More buying activity)"
    elif len(stats['sell_signals']) > len(stats['buy_signals']) * 1.5:
        sentiment = "🔴 BEARISH (More selling activity)"
    else:
        sentiment = "🟡 NEUTRAL (Balanced activity)"
    
    print(f"\n📊 Market Sentiment: {sentiment}")
    
    # Top active influencers
    print(f"\n👑 Top 10 Most Active Influencers:")
    top_10 = sorted(stats["influencer_activity"].items(), key=lambda x: x[1]["total_volume"], reverse=True)[:10]
    for i, (name, data) in enumerate(top_10, 1):
        print(f"   {i}. {name[:30]:<30} - {data['total_volume']} swaps ({data['buys']} buys, {data['sells']} sells)")
    
    # Recent activity
    if stats["daily_activity"]:
        recent_dates = sorted(stats["daily_activity"].keys())[-7:]
        print(f"\n📅 Activity Last 7 Days:")
        for date in recent_dates:
            count = stats["daily_activity"][date]
            bar = "█" * min(count // 2, 50)
            print(f"   {date}: {bar} ({count} txs)")
    
    print("\n" + "=" * 70)

def save_results():
    """Save detailed results to JSON"""
    output = {
        "timestamp": datetime.now().isoformat(),
        "stats": {
            "total_wallets": stats["total_wallets"],
            "active_wallets": stats["active_wallets"],
            "inactive_wallets": stats["inactive_wallets"],
            "total_transactions": stats["total_transactions"],
            "buy_signals": len(stats["buy_signals"]),
            "sell_signals": len(stats["sell_signals"])
        },
        "influencer_activity": dict(stats["influencer_activity"]),
        "daily_activity": dict(stats["daily_activity"]),
        "buy_signals": stats["buy_signals"][:50],  # Top 50
        "sell_signals": stats["sell_signals"][:50]
    }
    
    with open("comprehensive_research.json", "w") as f:
        json.dump(output, f, indent=2, default=str)
    
    print(f"💾 Detailed results saved to: comprehensive_research.json")

if __name__ == "__main__":
    print("\n🚀 Starting Comprehensive On-Chain Research...\n")
    asyncio.run(research_all_wallets())
    print("\n✅ Analysis Complete! Check the generated charts.")
