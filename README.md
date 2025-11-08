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
   ```bash
   # Navigate to the src directory
   cd src
   
   # Run the bot
   python main.py
   ```
   
   **Windows:**
   ```powershell
   cd src
   python main.py
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
- `.env.example` - Template for environment variables (API keys)
- `.gitignore` - Specifies which files Git should ignore

### Configuration
- `config/config.py` - Trading parameters, strategy settings, and bot configuration
- `config/keys_template.py` - Alternative template showing required API key structure

### Source Code (`src/`)
- `main.py` - Main entry point that runs the trading bot loop
- `roostoo_client.py` - Handles all API communication with Roostoo exchange (v3 API)
- `horus_client.py` - Fetches historical price data from Horus API
- `strategy.py` - MACD trading strategy implementation and signal generation
- `trading_logger.py` - Logging system for trades, portfolio, and market data
- `dashboard.py` - Real-time web dashboard for monitoring bot performance

### Generated Data (`logs/`)
Auto-created directory containing:
- `trading_bot.log` - Main application log file
- `trade_history.json/csv` - Record of all executed trades
- `portfolio_history.json/csv` - Portfolio value over time
- `market_data.jsonl` - Historical market data snapshots
- `strategy_signals.jsonl` - All strategy decisions (BUY/SELL/HOLD)

### Supporting Directories
- `tests/` - Unit tests and strategy validation code
- `deploy/` - Deployment scripts for cloud setup (AWS, etc.)