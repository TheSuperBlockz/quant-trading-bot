# MACE策略交易机器人

基于MACD指标的自动交易机器人，专为Roostoo交易平台设计。

## 功能特点

- 📊 **MACE策略**: 基于MACD指标的交易决策
- 🔄 **自动交易**: 全自动买卖决策和执行
- 📈 **实时监控**: 本地可视化仪表盘
- 📝 **详细日志**: 完整的交易和性能记录
- ⚙️ **风险控制**: 内置仓位管理和风险控制

## 安装和运行

### 1. 环境设置

```bash
# 克隆项目
git clone <repository-url>
cd trading-bot

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入您的API密钥