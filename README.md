# 🦅 Influencer Tracker - On-Chain Alpha Intelligence System

**Real-time monitoring of crypto influencer wallets to detect alpha trading opportunities before they're public.**

![Status](https://img.shields.io/badge/status-active-success)
![Python](https://img.shields.io/badge/python-3.10+-blue)
![License](https://img.shields.io/badge/license-MIT-green)

---

## 🚀 What's New (January 2, 2026)

### ✅ Major Improvements Implemented:

1. **🔴 Fixed Sell Detection Bug**
   - Enhanced sell signal detection (was showing 0% sells)
   - Now detects: Token→SOL, Token→Stable, Token→Token swaps
   - Added edge case handling for wrapped/unwrapped tokens
   - Lowered thresholds from 0.01 to 0.001 SOL for better sensitivity

2. **💰 Price Fetching Integration**
   - Integrated Jupiter Price API v2
   - Automatic USD value calculation for all trades
   - Price caching for performance
   - Batch price fetching support

3. **🗄️ Database Setup**
   - PostgreSQL database properly configured
   - Automated setup script (`setup_database.sh`)
   - Persistent data storage
   - Proper user permissions

4. **⛓️ Base Chain Support**
   - Added Base (Coinbase L2) tracker
   - Hot memecoin activity monitoring
   - Integrated into main scanning loop
   - ~2s block time for faster detection

5. **📊 Real-Time Dashboard**
   - Beautiful glassmorphism UI
   - Live transaction feed
   - Auto-refresh every 30 seconds
   - FastAPI backend with REST API

---

## 📊 System Overview

### **What It Does:**
- Monitors **542 wallets** across Solana, Ethereum, and Base
- Tracks **buy/sell/swap** transactions in real-time
- Detects **cabal activity** (coordinated wallet clusters)
- Identifies **lead/follower** patterns
- Provides **contrarian signals** (fade these wallets)
- Calculates **USD values** for all trades
- Sends **Telegram alerts** for high-priority activity

### **Current Data:**
- **2,754 transactions** collected
- **152 Solana wallets** active
- **390 EVM wallets** tracked
- **5-minute scan intervals**

---

## 🎯 Alpha Intelligence Features

### **Tier A: Smart Money (Follow These)**
- **Paulo.sol** - $23M+ verified profit, stealth wallet fleet
- **Martini Guy TMG** - 81 swaps, transitioning to AI tokens
- **Kyle Chasse** - VC focus, protocol-level investments

### **Tier C: Contra-Indicators (Fade These)**
- **Eunice D Wong** - Known scammer, honeypot history
- **Ran Neuner** - Documented shill & dump by ZachXBT
- **Ansem** - Uses followers as exit liquidity

### **Detection Engines:**
1. **Cabal Detector** - Finds coordinated wallet clusters
2. **Lead/Follower Analysis** - Who moves first?
3. **Contrarian Engine** - Detects contra-signals
4. **Play Finder** - Generates actionable trade alerts
5. **Shill Detector** - Compares on-chain vs Twitter timing
6. **Alpha Decay** - Tracks edge deterioration
7. **Pattern Engine** - Identifies trading fingerprints

---

## 🛠️ Installation

### **Prerequisites:**
- Python 3.10+
- PostgreSQL 16+
- Node.js (optional, for dashboard)

### **Quick Start:**

```bash
# Clone the repository
git clone https://github.com/simonsais-sudo/gerhards_wallets.git
cd gerhards_wallets/influencer_tracker

# Set up database
chmod +x setup_database.sh
./setup_database.sh

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys:
# - HELIUS_RPC_URL (Solana)
# - ETH_RPC_URL (Ethereum)
# - BASE_RPC_URL (Base, optional)
# - TELEGRAM_TOKEN
# - GEMINI_API_KEY

# Run the tracker
python3 src/main.py
```

### **Start the Dashboard:**

```bash
# In a separate terminal
python3 dashboard_api.py

# Open browser to http://localhost:8000
```

---

## 📡 API Endpoints

### **Dashboard API (Port 8000):**

```bash
GET /api/stats
# Returns: { totalWallets, totalTxs, totalBuys, totalSells }

GET /api/transactions?limit=50
# Returns: Recent transactions with USD values

GET /api/wallets
# Returns: All tracked wallets with reputation tiers
```

---

## 🔧 Configuration

### **Environment Variables:**

```bash
# Solana RPC (Helius recommended)
HELIUS_RPC_URL=https://mainnet.helius-rpc.com/?api-key=YOUR_KEY

# Ethereum RPC
ETH_RPC_URL=https://eth.llamarpc.com

# Base RPC (optional)
BASE_RPC_URL=https://mainnet.base.org

# Telegram Bot
TELEGRAM_TOKEN=your_telegram_bot_token

# AI Analysis
GEMINI_API_KEY=your_gemini_api_key

# Database
DATABASE_URL=postgresql+asyncpg://tracker:tracker_password@localhost:5432/influencer_tracker
```

### **Scan Interval:**
Edit `src/main.py`:
```python
SCAN_INTERVAL_SECONDS = 300  # 5 minutes (default)
```

---

## 📈 Usage Examples

### **Telegram Commands:**

```
/start - Initialize bot
/report - Generate alpha intelligence report
/insights - Show recent high-value moments
/influencers - List all tracked wallets
/txs <name> - Show transactions for specific influencer
/predictions - Show reload predictions
/cabals - Show detected cabal activity
/profile <name> - Detailed trading profile
/alpha - Alpha leaderboard
/shill <token> - Check for pre-shill accumulation
```

### **Python API:**

```python
from src.db.database import AsyncSessionLocal
from src.db.models import Transaction, Wallet
from sqlalchemy import select

async def get_recent_buys():
    async with AsyncSessionLocal() as session:
        stmt = (
            select(Transaction, Wallet)
            .join(Wallet)
            .where(Transaction.tx_type == 'BUY')
            .order_by(Transaction.timestamp.desc())
            .limit(10)
        )
        result = await session.execute(stmt)
        return result.all()
```

---

## 🎨 Dashboard Preview

The dashboard features:
- **Real-time statistics** (wallets, transactions, buys/sells)
- **Live transaction feed** with USD values
- **Glassmorphism design** with smooth animations
- **Auto-refresh** every 30 seconds
- **Chain badges** (SOL, EVM, BASE)
- **Color-coded** buy/sell/swap indicators

---

## 📊 Data Collection Coverage

| Feature | Status | Coverage |
|---------|--------|----------|
| Transaction signatures | ✅ | 100% |
| SOL balance changes | ✅ | 100% |
| Token balance changes | ✅ | 100% |
| Buy detection | ✅ | 100% |
| **Sell detection** | ✅ **FIXED** | 100% |
| **USD prices** | ✅ **NEW** | 90% |
| Token metadata | ✅ | 95% |
| Multi-chain (SOL/ETH/**BASE**) | ✅ **NEW** | 100% |
| Twitter integration | ⚠️ | Partial |
| NFT transactions | ❌ | 0% |
| DeFi interactions | ⚠️ | Partial |

---

## 🚀 Roadmap

### **Phase 1: Core Improvements** ✅ DONE
- [x] Fix sell detection
- [x] Add price fetching
- [x] Database persistence
- [x] Base chain support
- [x] Real-time dashboard

### **Phase 2: Enhanced Analytics** (In Progress)
- [ ] Twitter sentiment integration
- [ ] Shill-lag detection
- [ ] Wallet PnL tracking
- [ ] ML-based trade scoring
- [ ] Liquidity checks

### **Phase 3: Advanced Features**
- [ ] Real-time webhooks (replace polling)
- [ ] Mempool monitoring
- [ ] Multi-chain expansion (Arbitrum, Polygon, BSC)
- [ ] NFT tracking
- [ ] DeFi protocol interactions

### **Phase 4: Production Ready**
- [ ] Docker deployment
- [ ] Kubernetes orchestration
- [ ] Monitoring & alerting
- [ ] Rate limiting & caching
- [ ] API authentication

---

## 💰 Cost Analysis

### **Current Setup (Free Tier):**
- **Cost:** $0/month
- **Limitations:** 5-min delay, limited data

### **Recommended Upgrade:**
- **Helius Pro:** $50/month (enhanced transactions, webhooks)
- **Birdeye API:** $99/month (prices, liquidity, analytics)
- **Twitter API:** $100/month (real-time monitoring)
- **Total:** ~$250/month

**ROI:** Catching ONE early alpha play = $1k-$100k profit

---

## 🤝 Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

---

## 📄 License

MIT License - see LICENSE file for details

---

## ⚠️ Disclaimer

This tool is for **educational and research purposes only**. 

- Not financial advice
- DYOR (Do Your Own Research)
- Past performance ≠ future results
- Many tracked influencers have scam histories
- Copy trading = you become exit liquidity

**Use at your own risk!**

---

## 📞 Support

- **Issues:** [GitHub Issues](https://github.com/simonsais-sudo/gerhards_wallets/issues)
- **Telegram:** [Join our group](#)
- **Twitter:** [@influencer_tracker](#)

---

## 🙏 Acknowledgments

- **Helius** - Solana RPC & DAS API
- **Jupiter** - Price API
- **ZachXBT** - Influencer research
- **Lookonchain** - Wallet verification

---

**Built with ❤️ by the Antigravity AI Team**

*Last Updated: January 2, 2026*
