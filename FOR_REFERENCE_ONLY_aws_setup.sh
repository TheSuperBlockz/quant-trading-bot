#!/bin/bash
# Quick Start Script for AWS Deployment
# Run this on your AWS instance after uploading the code

echo "=========================================="
echo "Trading Bot - AWS Quick Setup"
echo "=========================================="
echo ""

# 1. Check Python version
echo "1. Checking Python version..."
python3 --version
if [ $? -ne 0 ]; then
    echo "❌ Python 3 not found. Install Python 3.8+ first."
    exit 1
fi
echo "✅ Python found"
echo ""

# 2. Navigate to project directory
echo "2. Navigating to project directory..."
cd ~/quant-trading-bot || { echo "❌ Project directory not found"; exit 1; }
echo "✅ In project directory: $(pwd)"
echo ""

# 3. Install dependencies
echo "3. Installing Python dependencies..."
pip3 install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "❌ Failed to install dependencies"
    exit 1
fi
echo "✅ Dependencies installed"
echo ""

# 4. Check for .env file
echo "4. Checking for .env file..."
if [ ! -f .env ]; then
    echo "⚠️  .env file not found!"
    echo "Creating template .env file..."
    cat > .env << 'EOF'
ROOSTOO_API_KEY=your_actual_production_api_key_here
ROOSTOO_SECRET=your_actual_production_secret_here
ROOSTOO_BASE_URL=https://mock-api.roostoo.com
HORUS_API_KEY=your_actual_horus_api_key_here
EOF
    echo "✅ Template .env created"
    echo "⚠️  IMPORTANT: Edit .env with your actual API keys before running the bot!"
    echo "   Run: nano .env"
    echo ""
    read -p "Press Enter after you've added your API keys to .env..."
else
    echo "✅ .env file exists"
fi
echo ""

# 5. Create logs directory
echo "5. Creating logs directory..."
mkdir -p logs
echo "✅ Logs directory ready"
echo ""

# 6. Test bot startup
echo "6. Testing bot startup (will run for 10 seconds)..."
echo "   Watch for initial trade execution..."
echo ""
timeout 10 python3 src/main.py || true
echo ""
echo "✅ Test run completed"
echo ""

# 7. Instructions
echo "=========================================="
echo "Setup Complete! Next Steps:"
echo "=========================================="
echo ""
echo "To start the bot for the competition:"
echo "  Option 1 (Recommended): Use screen"
echo "    screen -S trading-bot"
echo "    python3 src/main.py"
echo "    # Press Ctrl+A then D to detach"
echo ""
echo "  Option 2: Use nohup"
echo "    nohup python3 src/main.py > output.log 2>&1 &"
echo ""
echo "To monitor the bot:"
echo "  tail -f logs/trading_bot.log"
echo ""
echo "To check if bot is running:"
echo "  ps aux | grep main.py"
echo ""
echo "Competition Start: November 10, 2025, 8:00 PM"
echo "Initial Trade: $1.14 BTC (executes automatically)"
echo ""
echo "Good luck! 🚀"
echo "=========================================="
