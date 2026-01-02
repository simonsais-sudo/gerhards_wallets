"""
Test the updated /start message with top 20 influencers
"""

# Simulate realistic data based on your actual wallets
influencer_stats = {
    "Crypto Gains 1": {"EVM": 1, "SOL": 0, "total": 1},
    "Crypto Gains 2": {"EVM": 1, "SOL": 0, "total": 1},
    "Crypto Gains 9 (solana)": {"EVM": 0, "SOL": 1, "total": 1},
    "Alex Becker Main": {"EVM": 1, "SOL": 0, "total": 1},
    "Alex Becker Sidus Senate": {"EVM": 1, "SOL": 0, "total": 1},
    "Crypto Banter (Ran Neuner)": {"EVM": 1, "SOL": 0, "total": 1},
    "Crypto Banter 3 (Ran Neuner) (solana)": {"EVM": 0, "SOL": 1, "total": 1},
    "Jesse Eckel 7 (Solana)": {"EVM": 0, "SOL": 1, "total": 1},
    "Coach K 12 (solana)": {"EVM": 0, "SOL": 1, "total": 1},
    "Bitboy Crypto (Ben Armstrong) 1": {"EVM": 1, "SOL": 0, "total": 1},
    "EllioTrades 1": {"EVM": 1, "SOL": 0, "total": 1},
    "Brian Jung 4": {"EVM": 1, "SOL": 0, "total": 1},
    "Dr Profit 4 (solana)": {"EVM": 0, "SOL": 1, "total": 1},
    "CryptoGodJohn 1": {"EVM": 1, "SOL": 0, "total": 1},
    "Hustlepedia 1": {"EVM": 1, "SOL": 0, "total": 1},
    "Thor Hartvigsen 1": {"EVM": 1, "SOL": 0, "total": 1},
    "James Pelton 1": {"EVM": 1, "SOL": 0, "total": 1},
    "Bankless 1": {"EVM": 1, "SOL": 0, "total": 1},
    "Taiki Maeda 1": {"EVM": 1, "SOL": 0, "total": 1},
    "VirtualBacon 2": {"EVM": 1, "SOL": 0, "total": 1},
    "YourFriendAndy 1": {"EVM": 1, "SOL": 0, "total": 1},
    "Coinsider 1": {"EVM": 1, "SOL": 0, "total": 1},
}

# Add more to simulate > 20 influencers
for i in range(23, 35):
    influencer_stats[f"Influencer {i}"] = {"EVM": 1, "SOL": 0, "total": 1}

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

# Build summary line
if total_wallets > 0:
    summary_line = f"📊 *Tracking:* {total_influencers} influencers, {total_wallets} wallets\n\n"
else:
    summary_line = ""

welcome_text = (
    "👋 *Welcome to the Influencer Tracker Bot!*\n\n"
    "I am your dedicated blockchain watchdog, monitoring high-profile influencer wallets 24/7 on *Ethereum* and *Solana*.\n\n"
    f"{summary_line}"
    "*🏆 Top Tracked Influencers:*\n"
    f"{influencer_list}\n"
    "*💎 Subscription Modes:*\n"
    "1️⃣ *FREE:* Time-delayed alerts. See WHO is buying.\n"
    "2️⃣ *COPY TRADER:* Live alerts + Copy Trade Links.\n"
    "3️⃣ *RESEARCHER:* Full On-Chain Analysis + AI Safety Checks.\n\n"
    "_You are currently on the **FREE** plan._\n\n"
    "_Sit back and let the alpha come to you._ 🚀"
)

print("=" * 60)
print("PREVIEW: UPDATED /start MESSAGE")
print("=" * 60)
print("\n" + welcome_text)
print("\n" + "=" * 60)
print(f"\nTotal influencers: {total_influencers}")
print(f"Showing: {min(20, total_influencers)}")
print(f"Hidden: {max(0, total_influencers - 20)}")
