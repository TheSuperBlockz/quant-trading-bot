# Chill Alpha Quant Trading Bot

An automated trading bot using MACD (Moving Average Convergence Divergence) strategy for cryptocurrency trading on the Roostoo platform.

## Quick Start Guide

### Prerequisites
- Python 3.8 or higher
- Git (optional, for cloning)
- API keys from Roostoo and Horus

### Installation Steps

1. **Get the Code**
   ```bash
   # Option A: Clone from GitHub
   git clone https://github.com/TheSuperBlockz/quant-trading-bot.git
   cd quant-trading-bot
   
   # Option B: Download and extract the ZIP file
   # Then navigate to the extracted folder
   ```

2. **Install Dependencies**
   ```bash
   # Install required Python packages
   pip install -r requirements.txt
   ```

3. **Configure API Keys**
   ```bash
   # Create your .env file from the template
   cp .env.example .env
   
   # Edit .env and add your actual API keys:
   # - ROOSTOO_API_KEY
   # - ROOSTOO_SECRET
   # - HORUS_API_KEY
   ```
   
   **Windows PowerShell:**
   ```powershell
   Copy-Item .env.example .env
   # Then edit .env with your favorite text editor
   ```

4. **Run the Trading Bot**
   
   **For Testing (Paper Trading Mode):**
   ```bash
   # Run with simulated balance ($5M USD + 50 BTC)
   python paper_trading.py
   ```
   
   **For Real Trading (Competition/Live):**
   ```bash
   # Run with actual Roostoo API balance
   python src/main.py
   ```
   
   **Windows:**
   ```powershell
   # Paper trading mode
   python paper_trading.py
   
   # Real trading mode
   python src/main.py
   ```

5. **View the Dashboard (Optional)**
   - Once the bot is running, open your browser to: `http://localhost:8050`
   - The dashboard shows real-time portfolio value, price charts, and trade history

### Troubleshooting

**Missing Module Errors:**
```bash
pip install --upgrade -r requirements.txt
```

**API Connection Issues:**
- Verify your API keys in `.env` are correct
- Check that your API keys have trading permissions
- Ensure you have internet connectivity

**Dashboard Not Loading:**
- Make sure the bot is running
- Check if port 8050 is available (not used by another application)
- Try accessing `http://127.0.0.1:8050` instead

## Project Structure Overview

### Root Files
- `README.md` - This file: project documentation and setup instructions
- `requirements.txt` - Python dependencies required to run the trading bot
- `paper_trading.py` - **Paper trading mode** with simulated balance for testing
- `.env.example` - Template for environment variables (API keys)
- `.gitignore` - Specifies which files Git should ignore

### Configuration
- `config/config.py` - Trading parameters, strategy settings, and bot configuration
- `config/keys_template.py` - Alternative template showing required API key structure
- `config/keys.py` - User's actual API keys (not tracked in Git)

### Source Code (`src/`)
- `main.py` - **Real trading mode**: Main entry point using actual Roostoo API balance
- `roostoo_client.py` - Handles all API communication with Roostoo exchange (v3 API)
- `horus_client.py` - Fetches historical price data from Horus API for MACD calculations
- `strategy.py` - MACD trading strategy implementation and signal generation
- `trading_logger.py` - Logging system for trades, portfolio, and market data (saves to project root `/logs`)
- `dashboard.py` - Real-time web dashboard for monitoring bot performance (port 8050)

### Testing (`tests/`)
- `test_roostoo_api.py` - Interactive API testing tool to verify Roostoo endpoints and responses

### Generated Data (`logs/`)
Auto-created directory in project root containing:
- `trading_bot.log` - Main application log file with all bot activity
- `trade_history.json/csv` - Record of all executed trades
- `portfolio_history.json/csv` - Portfolio value snapshots over time
- `market_data.jsonl` - Historical market data from Roostoo ticker API
- `strategy_signals.jsonl` - All strategy decisions (BUY/SELL/HOLD) with reasoning

### Supporting Directories
- `deploy/` - Deployment scripts for cloud setup (AWS, etc.)

---

## Pre-Deployment Checklist (For Competition/Production)

Before deploying the trading bot to AWS or any production environment for the actual competition, complete these steps:

### 1. **Disable the Dashboard**
The dashboard is useful for local testing but should be disabled in production to reduce resource usage and potential security risks.

**In `src/main.py`, find the `__main__` section and set:**
```python
if __name__ == "__main__":
    bot = TradingBot(enable_dashboard=False)  # Set to False for production
    bot.run()
```

### 2. **Verify API Keys**
- Ensure your `.env` file contains the **production** API keys (not test/sandbox keys)
- Double-check that `ROOSTOO_API_KEY`, `ROOSTOO_SECRET`, and `HORUS_API_KEY` are correct
- Verify your Roostoo API keys have **trading permissions** enabled

### 3. **Test the Initial Trade**
The bot automatically executes a **$1.14 BTC purchase** on startup to satisfy the competition's 24-hour trade requirement. Before deploying:
```bash
# Run in paper trading mode to verify it works
python paper_trading.py

# Check logs to confirm initial trade executed:
# Should see "INITIAL TRADE: Executing $1.14 BUY to satisfy competition requirement"
```

### 4. **Check Strategy Parameters**
Review `config/config.py` for your final strategy settings:
- **MACD parameters**: Fast=12, Slow=26, Signal=9 (default)
- **Risk management**: 3% take profit, 3% stop loss, 1.5% trailing stop
- **Trade cooldown**: 1 hour between same-direction trades
- **Minimum trade**: $1 USD value, 0.00001 BTC amount

### 5. **Set Up Logging**
- Ensure the `logs/` directory will be writable on your deployment environment
- Consider setting up log rotation for long-running competitions
- Verify you can access logs remotely (AWS CloudWatch, etc.)

### 6. **Configure Auto-Restart**
For reliability in production:
- Use a process manager like `systemd`, `supervisor`, or `pm2`
- Configure auto-restart on crash
- Set up monitoring/alerting for bot downtime

### 7. **Timing for Competition Start**
- Competition starts: **November 10, 2025, 8:00 PM**
- The bot will immediately execute the $1.14 initial trade on first iteration
- Ensure bot is started **at or shortly after** 8:00 PM to begin trading

### 8. **Final Sanity Checks**
```bash
# Verify all dependencies are installed
pip install -r requirements.txt

# Test API connectivity (use the testing tool)
cd tests
python test_roostoo_api.py
# Select option 1 (Test Market Data) and 2 (Test Account Balance)

# Verify your starting balance is $50,000 USD (competition starting amount)
```

### 9. **Backup Configuration**
- Make a backup copy of your `.env` and `config/` files
- Keep a record of your deployment settings
- Document your AWS instance details (IP, region, instance type)

### 10. **Monitor the Bot**
After deployment:
- Watch the logs for the first few minutes to ensure proper startup
- Confirm the initial $1.14 BUY trade executed successfully
- Monitor for any API errors or connectivity issues
- Keep an eye on your balance and positions via the Roostoo web interface
