"""
Test script to verify transaction filter logic without requiring blockchain connection.
"""

import sys
sys.path.insert(0, '/Users/simonsais/gerhard_wallets/influencer_tracker')

from src.analysis.transaction_filter import TransactionFilter, TransactionImportance

def test_evm_filter():
    """Test EVM transaction filtering with mock data."""
    print("=" * 60)
    print("EVM TRANSACTION FILTER TESTS")
    print("=" * 60)
    
    filter_instance = TransactionFilter()
    
    # Mock Web3 instance
    class MockWeb3:
        @staticmethod
        def from_wei(value, unit):
            if unit == 'ether':
                return value / 1e18
            return value
    
    mock_w3 = MockWeb3()
    
    test_cases = [
        {
            "name": "Dust transaction",
            "tx": {
                "to": "0x1234567890123456789012345678901234567890",
                "value": 100000000000000,  # 0.0001 ETH
                "input": "0x"
            },
            "expected": TransactionImportance.SKIP
        },
        {
            "name": "Small ETH transfer",
            "tx": {
                "to": "0x1234567890123456789012345678901234567890",
                "value": 50000000000000000,  # 0.05 ETH
                "input": "0x"
            },
            "expected": TransactionImportance.LOW
        },
        {
            "name": "Medium ETH transfer",
            "tx": {
                "to": "0x1234567890123456789012345678901234567890",
                "value": 5000000000000000000,  # 5 ETH
                "input": "0x"
            },
            "expected": TransactionImportance.MEDIUM
        },
        {
            "name": "Large ETH transfer",
            "tx": {
                "to": "0x1234567890123456789012345678901234567890",
                "value": 15000000000000000000,  # 15 ETH
                "input": "0x"
            },
            "expected": TransactionImportance.HIGH
        },
        {
            "name": "Uniswap V2 swap",
            "tx": {
                "to": "0x7a250d5630b4cf539739df2c5dacb4c659f2488d",  # Uniswap V2 Router
                "value": 1000000000000000000,  # 1 ETH
                "input": "0x38ed17390000000000000000000000000000000000000000000000000000000000000001"  # swap function
            },
            "expected": TransactionImportance.HIGH
        },
        {
            "name": "ERC20 token transfer",
            "tx": {
                "to": "0xabcd567890123456789012345678901234567890",  # Some token contract
                "value": 0,
                "input": "0xa9059cbb0000000000000000000000001234567890123456789012345678901234567890"  # transfer()
            },
            "expected": TransactionImportance.MEDIUM
        }
    ]
    
    for i, test in enumerate(test_cases, 1):
        importance, reason = filter_instance.assess_evm_transaction(test["tx"], mock_w3)
        status = "✅ PASS" if importance == test["expected"] else "❌ FAIL"
        print(f"\n{i}. {test['name']}")
        print(f"   Expected: {test['expected'].name}")
        print(f"   Got: {importance.name}")
        print(f"   Reason: {reason}")
        print(f"   {status}")

def test_filter_decision():
    """Test the is_interesting decision logic."""
    print("\n" + "=" * 60)
    print("FILTER DECISION TESTS")
    print("=" * 60)
    
    filter_instance = TransactionFilter()
    
    test_cases = [
        (TransactionImportance.SKIP, False, "Should skip SKIP transactions"),
        (TransactionImportance.LOW, False, "Should skip LOW transactions"),
        (TransactionImportance.MEDIUM, True, "Should analyze MEDIUM transactions"),
        (TransactionImportance.HIGH, True, "Should analyze HIGH transactions"),
    ]
    
    for importance, expected_result, description in test_cases:
        result = filter_instance.is_interesting(importance)
        status = "✅ PASS" if result == expected_result else "❌ FAIL"
        print(f"\n{description}")
        print(f"   {importance.name} → {result} (expected {expected_result})")
        print(f"   {status}")

def test_dex_detection():
    """Test DEX swap detection."""
    print("\n" + "=" * 60)
    print("DEX SWAP DETECTION TESTS")
    print("=" * 60)
    
    filter_instance = TransactionFilter()
    
    test_cases = [
        ("0x38ed1739", True, "swapExactTokensForTokens"),
        ("0x7ff36ab5", True, "swapExactETHForTokens"),
        ("0x0", False, "Empty input"),
        ("0xa9059cbb", False, "ERC20 transfer (not a swap)"),
    ]
    
    for input_data, expected, description in test_cases:
        result = filter_instance._is_token_swap(input_data)
        status = "✅ PASS" if result == expected else "❌ FAIL"
        print(f"\n{description}")
        print(f"   Input: {input_data}")
        print(f"   Result: {result} (expected {expected})")
        print(f"   {status}")

def summary():
    """Print summary of what the filter does."""
    print("\n" + "=" * 60)
    print("FILTER BEHAVIOR SUMMARY")
    print("=" * 60)
    print("\n📊 Transaction Classification:")
    print("   • SKIP: No alert sent, no AI analysis")
    print("   • LOW: Basic alert only, no AI analysis")
    print("   • MEDIUM: Full alert + AI analysis")
    print("   • HIGH: Priority alert + AI analysis")
    
    print("\n🎯 EVM Thresholds:")
    print(f"   • Dust: < 0.001 ETH → SKIP")
    print(f"   • Small: < 0.1 ETH → LOW")
    print(f"   • Medium: 0.1 - 10 ETH → MEDIUM")
    print(f"   • Large: > 10 ETH → HIGH")
    print(f"   • DEX interactions: Upgraded to HIGH if swap detected")
    
    print("\n🎯 SOL Thresholds:")
    print(f"   • Dust: < 0.001 SOL → SKIP")
    print(f"   • Small: < 1 SOL → LOW")
    print(f"   • Medium: 1 - 100 SOL → MEDIUM")
    print(f"   • Large: > 100 SOL → HIGH")
    print(f"   • Spam: > 3 inner instructions → SKIP")
    
    print("\n💰 Expected Impact:")
    print("   • ~40-60% reduction in AI API calls")
    print("   • Higher quality alerts (less noise)")
    print("   • Better user experience (only meaningful moves)")

if __name__ == "__main__":
    test_evm_filter()
    test_filter_decision()
    test_dex_detection()
    summary()
    print("\n" + "=" * 60)
    print("TESTS COMPLETE")
    print("=" * 60)
