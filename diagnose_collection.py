#!/usr/bin/env python3
"""Diagnose what data is actually being collected by the RPC."""
import asyncio
import os
from datetime import datetime
from dotenv import load_dotenv
from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey

load_dotenv()

async def test_solana_rpc():
    """Test Solana RPC and show what data we can collect."""
    print("=" * 70)
    print("🔍 SOLANA RPC DIAGNOSTIC")
    print("=" * 70)
    
    rpc_url = os.getenv("HELIUS_RPC_URL", "")
    if not rpc_url:
        print("❌ No HELIUS_RPC_URL found in .env")
        return
    
    print(f"\n📡 RPC URL: {rpc_url[:50]}...")
    
    client = AsyncClient(rpc_url)
    
    # Test with Paulo.sol wallet (known active wallet)
    test_wallet = "6Yb9T2UkfeFT3F3RbMAwqVHzc2fRYXuMbmWxRGvJxGhN"  # Paulo.sol from config
    
    try:
        print(f"\n🎯 Testing with wallet: {test_wallet[:20]}...")
        pubkey = Pubkey.from_string(test_wallet)
        
        # Get signatures
        print("\n📝 Fetching last 5 signatures...")
        resp = await client.get_signatures_for_address(pubkey, limit=5)
        
        if not resp.value:
            print("   ❌ No signatures found")
            return
        
        print(f"   ✅ Found {len(resp.value)} recent transactions")
        
        # Analyze first transaction in detail
        sig_info = resp.value[0]
        sig = str(sig_info.signature)
        
        print(f"\n🔬 Analyzing transaction: {sig[:20]}...")
        print(f"   Block Time: {datetime.fromtimestamp(sig_info.block_time) if sig_info.block_time else 'Unknown'}")
        print(f"   Slot: {sig_info.slot}")
        
        # Get detailed transaction
        tx_resp = await client.get_transaction(
            sig_info.signature, 
            max_supported_transaction_version=0
        )
        
        if not tx_resp.value:
            print("   ❌ Could not fetch transaction details")
            return
        
        print("\n📊 DATA AVAILABLE:")
        
        # Check metadata
        meta = tx_resp.value.transaction.meta
        if meta:
            print("   ✅ Transaction metadata found")
            
            # SOL balances
            if meta.pre_balances and meta.post_balances:
                print(f"   ✅ SOL balance changes: {len(meta.pre_balances)} accounts")
            
            # Token balances
            if meta.pre_token_balances and meta.post_token_balances:
                print(f"   ✅ Token balance changes: {len(meta.post_token_balances)} tokens")
                
                # Show token details
                for token_bal in meta.post_token_balances[:3]:
                    mint = str(token_bal.mint)
                    amount = token_bal.ui_token_amount.ui_amount
                    print(f"      - Token: {mint[:20]}... Amount: {amount}")
            else:
                print("   ⚠️  No token balance data")
            
            # Fee
            if meta.fee:
                print(f"   ✅ Transaction fee: {meta.fee / 1e9} SOL")
            
            # Logs
            if meta.log_messages:
                print(f"   ✅ Program logs: {len(meta.log_messages)} messages")
                # Check for Jupiter/Raydium
                for log in meta.log_messages[:5]:
                    if 'Jupiter' in log or 'Raydium' in log or 'swap' in log.lower():
                        print(f"      🔥 DEX detected: {log[:60]}...")
        
        # Check instructions
        message = tx_resp.value.transaction.transaction.message
        if message:
            account_keys = message.account_keys
            print(f"   ✅ Account keys: {len(account_keys)} accounts involved")
            
            # Check for known programs
            known_programs = {
                "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4": "Jupiter Aggregator",
                "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8": "Raydium AMM",
                "9W959DqEETiGZocYWCQPaJ6sBmUzgfxXfqGeTEdp3aQP": "Orca",
            }
            
            for key in account_keys[:10]:
                key_str = str(key)
                if key_str in known_programs:
                    print(f"      🎯 Program: {known_programs[key_str]}")
        
        print("\n" + "=" * 70)
        print("✅ RPC is working and collecting data!")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        await client.close()

async def test_evm_rpc():
    """Test EVM RPC connection."""
    print("\n" + "=" * 70)
    print("🔍 EVM RPC DIAGNOSTIC")
    print("=" * 70)
    
    rpc_url = os.getenv("ETH_RPC_URL", "https://eth.llamarpc.com")
    print(f"\n📡 RPC URL: {rpc_url}")
    
    try:
        from web3 import AsyncWeb3
        w3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(rpc_url))
        
        # Test connection
        block_num = await w3.eth.block_number
        print(f"   ✅ Connected! Current block: {block_num}")
        
        # Get latest block
        block = await w3.eth.get_block('latest')
        print(f"   ✅ Latest block has {len(block['transactions'])} transactions")
        print(f"   ✅ Block timestamp: {datetime.fromtimestamp(block['timestamp'])}")
        
        print("\n" + "=" * 70)
        print("✅ EVM RPC is working!")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")

async def main():
    print("\n🚀 INFLUENCER TRACKER - RPC DIAGNOSTIC TOOL\n")
    
    await test_solana_rpc()
    await test_evm_rpc()
    
    print("\n📋 SUMMARY:")
    print("   - Check DATA_COLLECTION_ANALYSIS.md for improvement recommendations")
    print("   - Current data collection is WORKING but has gaps")
    print("   - Main issue: Sell signal detection needs improvement")
    print()

if __name__ == "__main__":
    asyncio.run(main())
