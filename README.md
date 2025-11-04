# Chill Alpha Quant Trading Bot - Project Structure Overview

## Root Files
- `README.md` - Project documentation, setup instructions, and competition details
- `requirements.txt` - Python dependencies required to run the trading bot

## Configuration
- `config/config.py` - Non-sensitive trading parameters and bot settings
- `config/keys_template.py` - Template showing required API key structure (copy to keys.py with real keys)

## Source Code
- `src/main.py` - Main entry point that runs the trading bot loop
- `src/roostoo_client.py` - Handles all API communication with Roostoo exchange
- `src/horus_client.py` - Fetches additional market data from Horus API
- `src/strategy.py` - Contains the core trading algorithm and decision logic
- `src/utils.py` - Helper functions for logging, calculations, and utilities

## Supporting Directories
- `logs/` - Stores trading activity logs and performance data (auto-created)
- `tests/` - Unit tests and strategy validation code
- `deploy/setup.sh` - AWS deployment script for cloud setup