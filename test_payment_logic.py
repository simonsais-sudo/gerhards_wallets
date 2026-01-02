
import asyncio
from unittest.mock import MagicMock, AsyncMock
from src.bot.payment import PaymentVerifier, PRICE_SOL_COPY_TRADER, PRICE_SOL_RESEARCHER, TREASURY_SOL

async def test_payment_logic():
    print(f"Testing Payment Logic with prices: CopyTrader={PRICE_SOL_COPY_TRADER}, Researcher={PRICE_SOL_RESEARCHER}")
    
    verifier = PaymentVerifier()
    # Mock the client
    verifier.client = AsyncMock()
    
    # Mock Transaction Response
    # We need to simulate the structure: resp.value.transaction.transaction.message.account_keys
    # and resp.value.meta.pre_balances / post_balances
    
    mock_resp = MagicMock()
    mock_value = MagicMock()
    mock_meta = MagicMock()
    mock_tx = MagicMock()
    mock_inner_tx = MagicMock()
    mock_message = MagicMock()
    
    mock_resp.value = mock_value
    mock_value.transaction = mock_tx
    mock_value.meta = mock_meta
    mock_tx.transaction = mock_inner_tx
    mock_inner_tx.message = mock_message
    
    mock_meta.err = None # Explicitly set no error
    
    # Setup Account Keys (Treasury at index 1)
    # Using the real treasury address to ensure logic matches
    mock_message.account_keys = ["SenderWalletAddress", TREASURY_SOL]
    
    # Helper to set balance change
    def set_sol_transfer(amount_sol):
        # 1 SOL = 1e9 lamports
        # Post - Pre = Amount
        # Let's say Pre = 0, Post = Amount
        mock_meta.pre_balances = [10000000000, 0] # Index 1 is Treasury
        mock_meta.post_balances = [10000000000 - int(amount_sol * 1e9), int(amount_sol * 1e9)]
        
    verifier.client.get_transaction.return_value = mock_resp
    
    # Test 1: Exact Researcher Payment (0.44 SOL)
    print("Test 1: Verifying Researcher Payment (0.44 SOL)...")
    set_sol_transfer(0.44)
    success, msg = await verifier.verify_sol_payment("9FL43JfMsqw577P6AyR3hkzSP5oF6ZxRNynzxe5Ad42D", "RESEARCHER")
    if success:
        print(f"✅ PASSED (Success: {msg})")
    else:
        print(f"❌ FAILED (Error: {msg})")

    # Test 2: Exact Copy Trader Payment (0.22 SOL)
    print("Test 2: Verifying Copy Trader Payment (0.22 SOL)...")
    set_sol_transfer(0.22)
    success, msg = await verifier.verify_sol_payment("9FL43JfMsqw577P6AyR3hkzSP5oF6ZxRNynzxe5Ad42D", "COPY_TRADER")
    if success:
        print(f"✅ PASSED (Success: {msg})")
    else:
        print(f"❌ FAILED (Error: {msg})")

    # Test 3: Insufficient Payment (0.1 SOL)
    print("Test 3: Verifying Insufficient Payment (0.1 SOL for Copy Trader)...")
    set_sol_transfer(0.1)
    success, msg = await verifier.verify_sol_payment("9FL43JfMsqw577P6AyR3hkzSP5oF6ZxRNynzxe5Ad42D", "COPY_TRADER")
    if not success:
        print(f"✅ PASSED (Correctly rejected: {msg})")
    else:
        print(f"❌ FAILED (Incorrectly accepted)")

    # Test 4: Slightly different amount (0.23 SOL) - Excess should be allowed
    print("Test 4: Verifying Excess Payment (0.23 SOL for Copy Trader)...")
    set_sol_transfer(0.23)
    success, msg = await verifier.verify_sol_payment("9FL43JfMsqw577P6AyR3hkzSP5oF6ZxRNynzxe5Ad42D", "COPY_TRADER")
    if success:
        print(f"✅ PASSED (Success: {msg})")
    else:
        print(f"❌ FAILED (Error: {msg})")

if __name__ == "__main__":
    asyncio.run(test_payment_logic())
