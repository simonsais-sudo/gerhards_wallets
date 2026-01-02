
import asyncio
import json
import re
from collections import defaultdict
from datetime import datetime, timedelta

def parse_token_received(tx_text):
    if not tx_text: return None
    tx_text = tx_text.lower()
    if "swapped" in tx_text:
        tokens = re.findall(r'[\d\.,]+\s+([\$a-z0-9_]{2,10})', tx_text)
        for t in tokens:
            t = t.replace('$', '').strip().upper()
            if t not in ['SOL', 'USDC', 'USDT', 'WSOL', 'FOR', 'SWAPPED', 'K']:
                return t
    return None

async def historical_stealth_discovery():
    with open('/Volumes/SD/Mac/gerhard_wallets/influencer_tracker/comprehensive_research.json', 'r') as f:
        data = json.load(f)
        
    print("\n" + "="*60)
    print("🕵️ HISTORICAL STEALTH DISCOVERY (Offline Analysis)")
    print("="*60)

    # 1. Shadow Cluster Discovery
    # Find wallets that trade the same token on the same day
    token_trades = defaultdict(list)
    for signal in data.get('buy_signals', []):
        token = parse_token_received(signal.get('tx', ''))
        if token:
            token_trades[token].append({
                'wallet': signal.get('wallet'),
                'date': signal.get('date')
            })

    shadow_links = defaultdict(int)
    for token, events in token_trades.items():
        # Group by date
        by_date = defaultdict(list)
        for e in events:
            by_date[e['date']].append(e['wallet'])
            
        for date, wallets in by_date.items():
            if len(wallets) >= 2:
                # Potential Shadow Link - multiple wallets buying same token same day
                unique_wallets = sorted(list(set(wallets)))
                for i in range(len(unique_wallets)):
                    for j in range(i+1, len(unique_wallets)):
                        pair = (unique_wallets[i], unique_wallets[j])
                        shadow_links[pair] += 1

    print("\n🔗 DISCOVERED SHADOW LINKS (Wallets trading together):")
    sorted_shadows = sorted(shadow_links.items(), key=lambda x: x[1], reverse=True)
    
    found = False
    for (w1, w2), count in sorted_shadows:
        if count >= 2: # At least 2 shared trades
            print(f"• {w1[:25]} <--> {w2[:25]} | {count} shared trades")
            found = True
    
    if not found:
        print("   No strong shadow clusters found in this data sample.")

    print("\n🔮 POTENTIAL STEALTH LEAD WALLETS:")
    # Wallets that buy something that others buy later
    leads = defaultdict(int)
    for token, events in token_trades.items():
        events.sort(key=lambda x: x['date'])
        if len(events) >= 2:
            first_wallet = events[0]['wallet']
            leads[first_wallet] += 1
            
    sorted_leads = sorted(leads.items(), key=lambda x: x[1], reverse=True)
    for wallet, count in sorted_leads[:5]:
        print(f"• {wallet[:30]} | Lead entry on {count} tokens")

if __name__ == "__main__":
    asyncio.run(historical_stealth_discovery())
