import logging
from enum import Enum
from typing import Dict, Tuple, Any, Optional

logger = logging.getLogger(__name__)

class TransactionImportance(Enum):
    """Classification of transaction importance for alert filtering."""
    SKIP = 0      # Don't alert (spam, dust, failed tx)
    LOW = 1       # Minor activity (small transfers)
    MEDIUM = 2    # Moderate interest (token swaps, NFT activity)
    HIGH = 3      # High priority (large swaps, unusual patterns)

class TransactionFilter:
    """
    Intelligent transaction classifier that determines if a transaction
    is worth analyzing with AI or sending alerts about.
    """
    
    # Thresholds (configurable)
    MIN_ETH_VALUE = 0.1  # Minimum ETH to be considered interesting
    MIN_SOL_VALUE = 1.0  # Minimum SOL to be considered interesting
    DUST_THRESHOLD = 0.001  # Below this is considered dust
    HIGH_VALUE_ETH = 10.0  # Above this is HIGH importance
    HIGH_VALUE_SOL = 100.0  # Above this is HIGH importance
    MAX_INNER_INSTRUCTIONS = 3  # More than this suggests spam/dusting
    
    def __init__(self):
        # Known spam/dust program IDs (Solana)
        self.solana_spam_programs = {
            # Add known airdrop/spam program IDs here
            "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",  # Will filter by behavior instead
        }
        
        # Known DEX program IDs (Solana)
        self.solana_dex_programs = {
            "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4",  # Jupiter
            "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc",  # Orca Whirlpool
            "9W959DqEETiGZocYWCQPaJ6sBmUzgfxXfqGeTEdp3aQP",  # Orca
            "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",  # Raydium AMM
        }
        
        # Known DEX router addresses (EVM)
        self.evm_dex_routers = {
            "0x7a250d5630b4cf539739df2c5dacb4c659f2488d",  # Uniswap V2 Router
            "0xe592427a0aece92de3edee1f18e0157c05861564",  # Uniswap V3 Router
            "0x68b3465833fb72a70ecdf485e0e4c7bd8665fc45",  # Uniswap V3 Router 2
            "0xd9e1ce17f2641f24ae83637ab66a2cca9c378b9f",  # Sushiswap Router
            "0x1111111254eeb25477b68fb85ed929f73a960582",  # 1inch V5 Router
        }
    
    def assess_solana_transaction(
        self, 
        tx_value: Dict[str, Any], 
        wallet_address: str
    ) -> Tuple[TransactionImportance, str]:
        """
        Assess a Solana transaction's importance.
        
        Args:
            tx_value: Transaction response from Solana RPC
            wallet_address: The wallet address being tracked
            
        Returns:
            Tuple of (importance_level, reason)
        """
        try:
            meta = tx_value.transaction.meta
            
            # Check if transaction failed
            if meta and meta.err:
                return (TransactionImportance.SKIP, "Transaction failed")
            
            # Check for excessive inner instructions (spam indicator)
            inner_count = len(meta.inner_instructions) if meta and meta.inner_instructions else 0
            if inner_count > self.MAX_INNER_INSTRUCTIONS:
                return (TransactionImportance.SKIP, f"Suspected spam (too many inner instructions: {inner_count})")
            
            # Extract program IDs from transaction
            program_ids = set()
            if tx_value.transaction.transaction.message:
                for key in tx_value.transaction.transaction.message.account_keys:
                    program_ids.add(str(key))
            
            # Check for DEX interaction (HIGH interest)
            dex_interaction = any(pid in self.solana_dex_programs for pid in program_ids)
            if dex_interaction:
                return (TransactionImportance.HIGH, "DEX swap detected")
            
            # Analyze SOL balance changes
            sol_change = 0
            if meta and meta.pre_balances and meta.post_balances:
                # Find wallet's index in account keys
                account_keys = tx_value.transaction.transaction.message.account_keys
                wallet_index = -1
                for idx, key in enumerate(account_keys):
                    if str(key) == wallet_address:
                        wallet_index = idx
                        break
                
                if wallet_index >= 0 and wallet_index < len(meta.pre_balances):
                    pre_balance = meta.pre_balances[wallet_index] / 1e9  # Convert lamports to SOL
                    post_balance = meta.post_balances[wallet_index] / 1e9
                    sol_change = abs(post_balance - pre_balance)
            
            # Classify by value
            if sol_change < self.DUST_THRESHOLD:
                return (TransactionImportance.SKIP, f"Dust transaction ({sol_change:.6f} SOL)")
            elif sol_change < self.MIN_SOL_VALUE:
                return (TransactionImportance.LOW, f"Small transfer ({sol_change:.4f} SOL)")
            elif sol_change < self.HIGH_VALUE_SOL:
                return (TransactionImportance.MEDIUM, f"Moderate activity ({sol_change:.2f} SOL)")
            else:
                return (TransactionImportance.HIGH, f"Large transfer ({sol_change:.2f} SOL)")
                
        except Exception as e:
            logger.error(f"Error assessing Solana transaction: {e}")
            # Default to MEDIUM on error to be safe
            return (TransactionImportance.MEDIUM, "Unable to classify (error)")
    
    def assess_evm_transaction(
        self,
        tx: Dict[str, Any],
        w3: Any  # Web3 instance
    ) -> Tuple[TransactionImportance, str]:
        """
        Assess an EVM transaction's importance.
        
        Args:
            tx: Transaction dict from Web3
            w3: Web3 instance for conversions
            
        Returns:
            Tuple of (importance_level, reason)
        """
        try:
            # Extract transaction details
            tx_to = tx.get('to')
            tx_value = tx.get('value', 0)
            tx_input = tx.get('input', '0x')
            
            # Convert value to ETH
            eth_value = float(w3.from_wei(tx_value, 'ether'))
            
            # Check if it's a contract interaction
            is_contract_call = tx_input and tx_input != '0x' and len(tx_input) > 10
            
            # Check for DEX interaction
            if tx_to and tx_to.lower() in self.evm_dex_routers:
                if eth_value > self.HIGH_VALUE_ETH or self._is_token_swap(tx_input):
                    return (TransactionImportance.HIGH, f"DEX swap on {self._get_dex_name(tx_to)}")
                else:
                    return (TransactionImportance.MEDIUM, f"DEX interaction on {self._get_dex_name(tx_to)}")
            
            # Contract interaction (could be interesting)
            if is_contract_call:
                if eth_value > self.HIGH_VALUE_ETH:
                    return (TransactionImportance.HIGH, f"Large contract interaction ({eth_value:.4f} ETH)")
                elif eth_value > self.MIN_ETH_VALUE:
                    return (TransactionImportance.MEDIUM, f"Contract interaction ({eth_value:.4f} ETH)")
                else:
                    # Contract call with no/low ETH - could be token transfer
                    # Check for ERC20 transfer signature
                    if tx_input.startswith('0xa9059cbb'):  # transfer(address,uint256)
                        return (TransactionImportance.MEDIUM, "Token transfer")
                    else:
                        return (TransactionImportance.LOW, "Minor contract interaction")
            
            # Simple ETH transfer
            if eth_value < self.DUST_THRESHOLD:
                return (TransactionImportance.SKIP, f"Dust transaction ({eth_value:.6f} ETH)")
            elif eth_value < self.MIN_ETH_VALUE:
                return (TransactionImportance.LOW, f"Small ETH transfer ({eth_value:.4f} ETH)")
            elif eth_value < self.HIGH_VALUE_ETH:
                return (TransactionImportance.MEDIUM, f"ETH transfer ({eth_value:.4f} ETH)")
            else:
                return (TransactionImportance.HIGH, f"Large ETH transfer ({eth_value:.2f} ETH)")
                
        except Exception as e:
            logger.error(f"Error assessing EVM transaction: {e}")
            return (TransactionImportance.MEDIUM, "Unable to classify (error)")
    
    def _is_token_swap(self, input_data: str) -> bool:
        """Check if input data suggests a token swap."""
        if not input_data or input_data == '0x':
            return False
        
        # Common swap function signatures
        swap_signatures = [
            '0x38ed1739',  # swapExactTokensForTokens
            '0x8803dbee',  # swapTokensForExactTokens
            '0x7ff36ab5',  # swapExactETHForTokens
            '0x18cbafe5',  # swapExactTokensForETH
            '0xfb3bdb41',  # swapETHForExactTokens
            '0x4a25d94a',  # swapTokensForExactETH
            '0x5c11d795',  # swapExactTokensForTokensSupportingFeeOnTransferTokens
            '0xb6f9de95',  # swapExactETHForTokensSupportingFeeOnTransferTokens
        ]
        
        return any(input_data.startswith(sig) for sig in swap_signatures)
    
    def _get_dex_name(self, address: str) -> str:
        """Get DEX name from router address."""
        dex_map = {
            "0x7a250d5630b4cf539739df2c5dacb4c659f2488d": "Uniswap V2",
            "0xe592427a0aece92de3edee1f18e0157c05861564": "Uniswap V3",
            "0x68b3465833fb72a70ecdf485e0e4c7bd8665fc45": "Uniswap V3",
            "0xd9e1ce17f2641f24ae83637ab66a2cca9c378b9f": "Sushiswap",
            "0x1111111254eeb25477b68fb85ed929f73a960582": "1inch",
        }
        return dex_map.get(address.lower(), "Unknown DEX")
    
    def is_interesting(self, importance: TransactionImportance) -> bool:
        """
        Determine if a transaction should trigger AI analysis and alerts.
        
        Args:
            importance: The importance level
            
        Returns:
            True if should analyze with AI, False to skip
        """
        return importance in [TransactionImportance.MEDIUM, TransactionImportance.HIGH]
