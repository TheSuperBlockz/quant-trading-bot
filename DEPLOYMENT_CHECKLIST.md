# AWS Deployment Checklist ✅

## Pre-Upload Verification

### ✅ Code Changes Applied
- [x] Dashboard disabled in `src/main.py` (enable_dashboard=False)
- [x] Initial trade set to $1.14 (meme amount)
- [x] Logging configured for production
- [x] Error handling with 60-second retry on exceptions

### ✅ Files to Upload
Upload the entire `quant-trading-bot` folder to AWS, ensuring these key files are included:
```
quant-trading-bot/
├── src/
│   ├── main.py              ← Main bot (PRODUCTION READY)
│   ├── roostoo_client.py
│   ├── horus_client.py
│   ├── strategy.py
│   ├── trading_logger.py
│   └── dashboard.py
├── config/
│   ├── config.py
│   └── keys.py              ← Your API keys (or use .env)
├── requirements.txt
├── .env                     ← YOUR PRODUCTION API KEYS
└── logs/                    ← Will be auto-created
```

### ⚠️ CRITICAL: API Keys Setup

**Option 1: Using .env file (Recommended)**
1. Create `.env` file on AWS instance with your PRODUCTION keys:
   ```bash
   ROOSTOO_API_KEY=your_actual_production_key
   ROOSTOO_SECRET=your_actual_production_secret
   ROOSTOO_BASE_URL=https://mock-api.roostoo.com
   HORUS_API_KEY=your_actual_horus_key
   ```

**Option 2: Using config/keys.py**
- Ensure `config/keys.py` has your production credentials
- Make sure this file is uploaded to AWS

### ✅ AWS Instance Setup

1. **Install Python 3.8+**
   ```bash
   python3 --version  # Verify Python is installed
   ```

2. **Upload Code to AWS**
   ```bash
   # Using SCP (from your local machine)
   scp -r quant-trading-bot/ ec2-user@your-aws-ip:/home/ec2-user/
   
   # Or use SFTP, AWS Console upload, or Git clone
   ```

3. **Install Dependencies**
   ```bash
   cd /home/ec2-user/quant-trading-bot
   pip3 install -r requirements.txt
   ```

4. **Test the Bot (Quick Check)**
   ```bash
   # Run for 2-3 minutes to verify it starts correctly
   python3 src/main.py
   
   # Watch for:
   # - "INITIAL TRADE: Executing $1.14 BUY to satisfy competition requirement"
   # - No API errors
   # - Bot polling every 60 seconds
   
   # Stop with Ctrl+C after verification
   ```

### ✅ Production Launch (Competition Start)

**Competition Starts: November 10, 2025, 8:00 PM**

**Option A: Using Screen (Recommended)**
```bash
# Start at 8:00 PM
screen -S trading-bot
cd /home/ec2-user/quant-trading-bot
python3 src/main.py

# Detach: Press Ctrl+A, then D
# Reattach later: screen -r trading-bot
```

**Option B: Using nohup**
```bash
# Start at 8:00 PM
cd /home/ec2-user/quant-trading-bot
nohup python3 src/main.py > output.log 2>&1 &

# Check it's running: ps aux | grep main.py
# View logs: tail -f output.log
```

**Option C: Using systemd (Most Robust)**
Create `/etc/systemd/system/trading-bot.service`:
```ini
[Unit]
Description=Quant Trading Bot
After=network.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/home/ec2-user/quant-trading-bot
ExecStart=/usr/bin/python3 /home/ec2-user/quant-trading-bot/src/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable trading-bot
sudo systemctl start trading-bot  # Start at 8:00 PM
sudo systemctl status trading-bot  # Check status
sudo journalctl -u trading-bot -f  # View logs
```

### ✅ Monitoring During Competition

1. **Check Initial Trade Executed**
   ```bash
   # View logs
   tail -f /home/ec2-user/quant-trading-bot/logs/trading_bot.log
   
   # Look for:
   # "EXECUTING INITIAL TRADE (Competition Requirement)"
   # "INITIAL TRADE: Executing $1.14 BUY"
   # "Initial trade executed successfully"
   ```

2. **Verify Trade in Roostoo**
   - Log into Roostoo web interface
   - Check trade history for $1.14 BTC purchase
   - Confirm balance: Should be ~$49,998.86 USD + small BTC amount

3. **Monitor Bot Health**
   ```bash
   # Check process is running
   ps aux | grep main.py
   
   # Check logs for errors
   grep -i error /home/ec2-user/quant-trading-bot/logs/trading_bot.log
   
   # Check recent activity
   tail -20 /home/ec2-user/quant-trading-bot/logs/trading_bot.log
   ```

4. **Trade History Files**
   ```bash
   # View executed trades
   cat /home/ec2-user/quant-trading-bot/logs/trade_history.json
   
   # Portfolio snapshots
   cat /home/ec2-user/quant-trading-bot/logs/portfolio_history.json
   ```

### ⚠️ Troubleshooting

**Bot Not Starting:**
- Check Python version: `python3 --version` (need 3.8+)
- Verify dependencies: `pip3 install -r requirements.txt`
- Check API keys in `.env` file
- Look for errors: `tail -50 /home/ec2-user/quant-trading-bot/logs/trading_bot.log`

**Initial Trade Failed:**
- Verify Roostoo balance is $50,000 USD
- Check API keys have trading permissions
- Ensure Roostoo API endpoint is correct
- Review logs for specific error message

**Bot Stops Running:**
- Use `screen` or `systemd` to keep it running
- Check system resources: `top` or `htop`
- Review error logs for crash reason

### ✅ Final Pre-Launch Checklist

- [ ] AWS instance running and accessible
- [ ] Python 3.8+ installed
- [ ] All code uploaded to AWS
- [ ] `.env` file with PRODUCTION API keys created
- [ ] Dependencies installed (`pip3 install -r requirements.txt`)
- [ ] Quick test run completed (2-3 minutes, then stopped)
- [ ] Process manager configured (screen/systemd/nohup)
- [ ] Logs directory is writable
- [ ] Roostoo web interface accessible for monitoring
- [ ] Ready to start bot at 8:00 PM on November 10, 2025

---

## Post-Competition

After the competition ends (November 11, 2025, 8:00 PM):

1. **Stop the bot**
   ```bash
   # If using screen
   screen -r trading-bot
   # Press Ctrl+C
   
   # If using systemd
   sudo systemctl stop trading-bot
   
   # If using nohup
   pkill -f main.py
   ```

2. **Download logs and results**
   ```bash
   # From your local machine
   scp -r ec2-user@your-aws-ip:/home/ec2-user/quant-trading-bot/logs/ ./competition-results/
   ```

3. **Review performance**
   - Trade history: `logs/trade_history.json`
   - Portfolio history: `logs/portfolio_history.json`
   - Final P&L in Roostoo interface

---

**Good luck with the competition! 🚀**
