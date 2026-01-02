"""
On-Chain Wallet Research Tool
Analyzes recent transactions from tracked influencer wallets
"""

import asyncio
import json
import os
from datetime import datetime, timedelta
from collections import defaultdict
import aiohttp
from dotenv import load_dotenv

load_dotenv()

HELIUS_API_KEY = "a6b6d793-f3d4-4d02-bc36-0a758ac735cf"
HELIUS_RPC_URL = os.getenv("HELIUS_RPC_URL", f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}")

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
    "errors": []
}

async def fetch_solana_transactions(session, address: str, limit: int = 10):
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

async def fetch_eth_transactions(session, address: str):
    """Fetch recent transactions for an EVM wallet using Etherscan-like API"""
    # Using public Etherscan API (limited but works for research)
    url = f"https://api.etherscan.io/api?module=account&action=txlist&address={address}&startblock=0&endblock=99999999&page=1&offset=10&sort=desc"
    
    try:
        async with session.get(url, timeout=10) as resp:
            if resp.status == 200:
                data = await resp.json()
                if data.get("status") == "1":
                    return data.get("result", [])
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
        stats["inactive_wallets"] += 1
        return None
    
    stats["active_wallets"] += 1
    stats["total_transactions"] += len(txs)
    
    # Analyze transactions
    wallet_data = {
        "name": name,
        "address": address,
        "chain": "SOL",
        "tx_count": len(txs),
        "recent_activity": [],
        "tokens_traded": set(),
        "last_active": None
    }
    
    for tx in txs[:10]:  # Analyze last 10
        tx_type = tx.get("type", "UNKNOWN")
        description = tx.get("description", "")
        timestamp = tx.get("timestamp")
        
        # Track activity
        if timestamp and not wallet_data["last_active"]:
            wallet_data["last_active"] = datetime.fromtimestamp(timestamp).isoformat()
        
        # Look for swaps
        if tx_type == "SWAP":
            # Extract token info
            token_transfers = tx.get("tokenTransfers", [])
            for transfer in token_transfers:
                token_mint = transfer.get("mint", "Unknown")
                wallet_data["tokens_traded"].add(token_mint[:16] + "...")
                stats["token_activity"][token_mint] += 1
            
            wallet_data["recent_activity"].append({
                "type": "SWAP",
                "description": description[:100] if description else "Token swap",
                "time": datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M") if timestamp else "Unknown"
            })
            
            # Check if buy or sell (more accurate classification)
            desc_lower = description.lower()
            is_sell = any(x in desc_lower for x in ["to sol", "to usdc", "to usdt", "for sol", "for usdc", "for usdt"])
            
            # Additional check: if they gave away a token and received SOL/Stable, it's a sell
            # Helius descriptions usually follow: "Wallet swapped [TokenA] for [TokenB]"
            if "swapped" in desc_lower:
                parts = desc_lower.split("for")
                if len(parts) > 1:
                    target = parts[1].strip()
                    if any(s in target for s in ["sol", "usdc", "usdt"]):
                        is_sell = True
            
            if is_sell:
                stats["sell_signals"].append({"wallet": name, "tx": description[:80]})
            else:
                stats["buy_signals"].append({"wallet": name, "tx": description[:80]})
        
        elif tx_type == "TRANSFER":
            wallet_data["recent_activity"].append({
                "type": "TRANSFER",
                "description": description[:100] if description else "Transfer",
                "time": datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M") if timestamp else "Unknown"
            })
    
    wallet_data["tokens_traded"] = list(wallet_data["tokens_traded"])
    return wallet_data

async def research_wallets(sample_size: int = 30):
    """Main research function - samples wallets and analyzes activity"""
    
    # Load wallets
    with open("config/wallets.json", "r") as f:
        all_wallets = json.load(f)
    
    # Separate by chain
    sol_wallets = [w for w in all_wallets if w.get("chain") == "SOL"]
    evm_wallets = [w for w in all_wallets if w.get("chain") == "EVM"]
    
    print("=" * 70)
    print("🔍 ON-CHAIN WALLET RESEARCH")
    print("=" * 70)
    print(f"\n📊 Wallet Database:")
    print(f"   • Total Wallets: {len(all_wallets)}")
    print(f"   • Solana Wallets: {len(sol_wallets)}")
    print(f"   • EVM Wallets: {len(evm_wallets)}")
    
    # Sample SOL wallets (API-friendly)
    sample_sol = sol_wallets[:min(sample_size, len(sol_wallets))]
    
    print(f"\n🔎 Researching {len(sample_sol)} Solana wallets...")
    print("   (Using Helius API - free tier has limits)\n")
    
    stats["total_wallets"] = len(sample_sol)
    
    async with aiohttp.ClientSession() as session:
        results = []
        
        for i, wallet in enumerate(sample_sol):
            print(f"   [{i+1}/{len(sample_sol)}] Checking {wallet['name'][:40]}...", end="\r")
            result = await analyze_solana_wallet(session, wallet)
            if result:
                results.append(result)
            await asyncio.sleep(0.3)  # Rate limit protection
        
        print("\n")
    
    # Print Results
    print("=" * 70)
    print("📈 RESEARCH RESULTS")
    print("=" * 70)
    
    print(f"\n📊 Activity Summary:")
    print(f"   • Wallets Analyzed: {stats['total_wallets']}")
    print(f"   • Active (recent txs): {stats['active_wallets']}")
    print(f"   • Inactive: {stats['inactive_wallets']}")
    print(f"   • Total Transactions Found: {stats['total_transactions']}")
    
    print(f"\n🔥 Buy Signals (Recent): {len(stats['buy_signals'])}")
    for sig in stats["buy_signals"][:5]:
        print(f"   • {sig['wallet']}: {sig['tx'][:60]}...")
    
    print(f"\n❄️ Sell Signals (Recent): {len(stats['sell_signals'])}")
    for sig in stats["sell_signals"][:5]:
        print(f"   • {sig['wallet']}: {sig['tx'][:60]}...")
    
    # Most traded tokens
    if stats["token_activity"]:
        print(f"\n🪙 Most Active Tokens:")
        sorted_tokens = sorted(stats["token_activity"].items(), key=lambda x: x[1], reverse=True)[:10]
        for token, count in sorted_tokens:
            print(f"   • {token[:20]}...: {count} trades")
    
    # Most active wallets
    active_wallets = sorted(results, key=lambda x: x["tx_count"], reverse=True)[:10]
    print(f"\n👑 Most Active Wallets:")
    for w in active_wallets:
        last = w.get("last_active", "Unknown")
        print(f"   • {w['name'][:35]}: {w['tx_count']} txs (Last: {last[:10] if last else 'N/A'})")
    
    # Recent activity details
    print(f"\n📜 Recent Swap Activity (Last 7 days):")
    swap_count = 0
    for r in results:
        for activity in r.get("recent_activity", []):
            if activity["type"] == "SWAP":
                swap_count += 1
                if swap_count <= 15:
                    print(f"   [{activity['time']}] {r['name'][:25]}: {activity['description'][:50]}...")
    
    if swap_count == 0:
        print("   No recent swaps detected in sampled wallets")
    else:
        print(f"\n   Total swaps found: {swap_count}")
    
    # Errors
    if stats["errors"]:
        print(f"\n⚠️ Errors ({len(stats['errors'])}):")
        for err in stats["errors"][:5]:
            print(f"   • {err}")
    
    print("\n" + "=" * 70)
    print("✅ RESEARCH COMPLETE")
    print("=" * 70)
    
    # Save results
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
        "buy_signals": stats["buy_signals"],
        "sell_signals": stats["sell_signals"],
        "active_wallets_detail": results
    }
    
    with open("research_results.json", "w") as f:
        json.dump(output, f, indent=2, default=str)
    
    print(f"\n💾 Results saved to: research_results.json")
    
    return output

if __name__ == "__main__":
    print("\n🚀 Starting On-Chain Research...\n")
    asyncio.run(research_wallets(sample_size=50))
