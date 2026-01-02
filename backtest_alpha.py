
import json
import re
from collections import defaultdict
from datetime import datetime

def parse_token_received(tx_text):
    if not tx_text: return None
    tx_text = tx_text.lower()
    if "swapped" in tx_text:
        # Better extraction: look for symbols like AI, BODEN, etc.
        # Often after a number and before "for" or at the end
        tokens = re.findall(r'[\d\.,]+\s+([\$a-z0-9_]{2,10})', tx_text)
        for t in tokens:
            t = t.replace('$', '').strip().upper()
            if t not in ['SOL', 'USDC', 'USDT', 'WSOL', 'FOR', 'SWAPPED', 'K']:
                return t
    return None

def backtest_alpha():
    with open('/Volumes/SD/Mac/gerhard_wallets/influencer_tracker/comprehensive_research.json', 'r') as f:
        data = json.load(f)
        
    # Tier Definition
    LEAD_NAMES = ["paulo.sol", "Kyle Chasse", "Martini Guy"]
    FOLLOWER_NAMES = ["Ansem", "Crypto Banter", "Ran Neuner", "Eunice Wong", "Coach K", "Dr Profit", "Invest Answers", "Fefe", "Kyle Doops"]
    
    token_history = defaultdict(list)
    
    for signal in data.get('buy_signals', []):
        wallet = signal.get('wallet', 'Unknown')
        tx = signal.get('tx', '')
        date = signal.get('date', 'Unknown')
        token = parse_token_received(tx)
        
        if token:
            print(f"DEBUG: Found token {token} from {wallet}")
            # Determine Tier
            tier = 'U'
            if any(name in wallet for name in LEAD_NAMES): tier = 'A'
            elif any(name in wallet for name in FOLLOWER_NAMES): tier = 'B'
            
            token_history[token].append({
                'wallet': wallet,
                'tier': tier,
                'date': date,
                'tx': tx
            })

    print("\n" + "="*70)
    print("📜 HISTORICAL ALPHA AUDIT: LEADS VS FOLLOWERS")
    print("="*70)

    for token, events in token_history.items():
        # Sort by date
        events.sort(key=lambda x: x['date'])
        
        leads = [e for e in events if e['tier'] == 'A']
        followers = [e for e in events if e['tier'] == 'B']
        
        if leads and followers:
            first_lead = leads[0]
            first_follower = followers[0]
            
            # Check if Lead was actually first
            if first_lead['date'] <= first_follower['date']:
                print(f"\n✅ ALPHA GAP VALIDATED: ${token}")
                print(f"   ∟ LEAD ENTRY:     {first_lead['wallet']} on {first_lead['date']}")
                print(f"   ∟ FOLLOWER ENTRY: {first_follower['wallet']} on {first_follower['date']}")
                if first_lead['date'] < first_follower['date']:
                    print(f"   🚀 PROFIT WINDOW: {first_lead['date']} to {first_follower['date']} (Frontrun successful)")
                else:
                    print(f"   ⚡ SAME DAY ENTRY: Likely Cabal/Coordinated call.")
            else:
                print(f"\n⚠️ INVERSE PATTERN: ${token}")
                print(f"   ∟ Shiller {first_follower['wallet']} entered before Whale {first_lead['wallet']}.")

if __name__ == "__main__":
    backtest_alpha()
