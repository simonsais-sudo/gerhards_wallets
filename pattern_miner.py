
import json
import re
from collections import defaultdict
from datetime import datetime

def parse_token_received(tx_text):
    if not tx_text: return None
    tx_text = tx_text.lower()
    
    # Extract Received Token (Bought)
    # Helius logic: "swapped [Amount] [SourceToken] for [Amount] [TargetToken]"
    if "swapped" in tx_text and "for" in tx_text:
        # Check for SOL/USDC/USDT as target (this would be a SELL of something else)
        if any(x in tx_text.split("for")[-1] for x in ["sol", "usdc", "usdt"]):
            return None # This is a sell signal
            
        # Target token is after "for [Amount]"
        match = re.search(r'for\s+[\d\.,]+\s+([\$a-z0-9_]+)', tx_text)
        if match:
            token = match.group(1).replace('$', '').strip().upper()
            if token not in ['SOL', 'USDC', 'USDT', 'WSOL']:
                return token
                
    return None

def mine_patterns():
    try:
        with open('/Volumes/SD/Mac/gerhard_wallets/influencer_tracker/comprehensive_research.json', 'r') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error loading data: {e}")
        return
        
    token_to_influencers = defaultdict(set)
    influencer_to_tokens = defaultdict(list)
    
    # Process both buy_signals (which might contain wrongly classified sells) 
    # and look for consistent tokens
    for signal in data.get('buy_signals', []):
        wallet = signal.get('wallet', 'Unknown')
        tx = signal.get('tx', '')
        date = signal.get('date', 'Unknown')
        
        token = parse_token_received(tx)
        if token:
            token_to_influencers[token].add(wallet)
            influencer_to_tokens[wallet].append({'token': token, 'date': date})

    # 1. Multi-Influencer Clusters (Potential Alpha)
    clusters = []
    for token, influencers in token_to_influencers.items():
        if len(influencers) >= 1: # Reduced to 1 to see all tokens first
            clusters.append({
                'token': token,
                'count': len(influencers),
                'influencers': list(influencers)
            })
            
    clusters.sort(key=lambda x: x['count'], reverse=True)
    
    print("\n" + "="*60)
    print("💎 PATTERN MINER: THE INNER CIRCLE ALPHA")
    print("="*60)
    
    print("\n🚀 TOKENS BEING ACCUMULATED (Cluster Analysis):")
    if not clusters:
        print("No coordinated buy clusters found in current data.")
    for c in clusters[:15]:
        status = "🕸️ CABAL!" if c['count'] > 1 else "🔍 Single Buyer"
        print(f"• ${c['token']:<12} | {c['count']} Influencers | {status} | {', '.join(c['influencers'][:3])}")

    # 2. The "Insane Convicton" Play
    print("\n📈 HIGH CONVICTION PLAYS (Repeated buys by same entity):")
    convictions = []
    for wallet, tokens in influencer_to_tokens.items():
        counts = defaultdict(int)
        for t in tokens:
            counts[t['token']] += 1
        for token, count in counts.items():
            if count >= 2:
                convictions.append({'wallet': wallet, 'token': token, 'buys': count})
                
    convictions.sort(key=lambda x: x['buys'], reverse=True)
    for conv in convictions[:10]:
        print(f"• {conv['wallet'][:30]:<30} heavy on ${conv['token']} ({conv['buys']} buys)")

    # 3. Strategy Idea: "The Follower Lag"
    print("\n💡 TRADING IDEA: THE 'ANSEM LAG'")
    print("If Martini Guy (Activity Leader) buys a token that Paulo.sol (Profit Leader) holds,")
    print("this is a high-probability rotation play.")

if __name__ == "__main__":
    mine_patterns()
