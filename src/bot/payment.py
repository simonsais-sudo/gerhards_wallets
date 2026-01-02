
import logging
import os
from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey
from sqlalchemy import select
from src.db.database import AsyncSessionLocal
from src.db.models import User

logger = logging.getLogger(__name__)

# Constants (Placeholder addresses - User must replace these or set via ENV)
TREASURY_SOL = os.getenv("TREASURY_SOL", "9FL43JfMsqw577P6AyR3hkzSP5oF6ZxRNynzxe5Ad42D") 
TREASURY_EVM = os.getenv("TREASURY_EVM", "YourEVMWalletAddressHere")

# Prices (in SOL)
PRICE_SOL_COPY_TRADER = 0.22 
PRICE_SOL_RESEARCHER = 0.44

class PaymentVerifier:
    def __init__(self):
        self.sol_rpc_url = os.getenv("HELIUS_RPC_URL", "https://api.mainnet-beta.solana.com")
        self.client = AsyncClient(self.sol_rpc_url)
        
    async def verify_sol_payment(self, tx_hash: str, expected_tier: str) -> bool:
        """
        Verify if a SOL transaction matches the subscription requirements.
        Returns (True, "Success") or (False, "Reason").
        """
        try:
            # Clean hash
            tx_hash = tx_hash.strip()
            
            # Fetch transaction
            # Using max_supported_transaction_version=0 for v0 support
            resp = await self.client.get_transaction(
                Pubkey.from_string(tx_hash) if isinstance(tx_hash, str) else tx_hash, 
                max_supported_transaction_version=0
            )

            if not resp.value:
                return False, "Transaction not found on Solana chain."
            
            # Check receiver and amount
            transaction = resp.value.transaction
            meta = resp.value.meta
            
            if not meta:
                return False, "Transaction metadata not found."
                
            if meta.err:
                return False, "Transaction failed on-chain."

            # Calculate amount transferred to Treasury
            # We need to look at pre_balances and post_balances
            # Find the index of the treasury account in the account keys
            
            account_keys = transaction.transaction.message.account_keys
            # For v0 transactions, account keys might be in lookups, but typically main accounts are in account_keys
            # We simplify by checking pre/post balances of all accounts matching our treasury
            
            treasury_pubkey_str = TREASURY_SOL
            found_index = -1
            
            # Convert account keys to strings for comparison
            # Note: solders Transaction object structure
            all_accounts = [str(k) for k in account_keys]
            
            try:
                found_index = all_accounts.index(treasury_pubkey_str)
            except ValueError:
                # Treasury not involved in this transaction directly
                return False, f"Treasury wallet ({treasury_pubkey_str}) not involved in this transaction."

            pre_bal = meta.pre_balances[found_index]
            post_bal = meta.post_balances[found_index]
            
            amount_received = (post_bal - pre_bal) / 1e9 # Lamports to SOL
            
            required_amount = 0.0
            if expected_tier == "COPY_TRADER":
                required_amount = PRICE_SOL_COPY_TRADER
            elif expected_tier == "RESEARCHER":
                required_amount = PRICE_SOL_RESEARCHER
            
            # Allow small leniency for float math? No, crypto is precise. 
            # But maybe user sent 0.51? We check if >= required (active subscription)
            if amount_received >= required_amount * 0.98: # 2% slippage allowance just in case (unlikely for transfer but good UX)
                 return True, f"Payment verified! Received {amount_received:.4f} SOL."
            else:
                 return False, f"Insufficient amount. Received {amount_received:.4f} SOL, required {required_amount} SOL."

        except Exception as e:
            logger.error(f"Payment verification refused: {e}")
            return False, f"Error verifying transaction: {str(e)}"

    async def close(self):
        await self.client.close()

payment_verifier = PaymentVerifier()
