
import sys
import os

# Add current dir to path
sys.path.append(os.getcwd())

try:
    from src.bot.payment import payment_verifier, PaymentVerifier
    print("✅ Payment module imported successfully")
except Exception as e:
    print(f"❌ Error importing src.bot.payment: {e}")

try:
    from src.bot.telegram_handler import TelegramBot
    print("✅ Telegram handler imported successfully")
except Exception as e:
    print(f"❌ Error importing src.bot.telegram_handler: {e}")
