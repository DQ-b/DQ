# DQ —— TqSdk + DeepSeek 自动化期货交易

## 文件
- `tqsdk_deepseek_arch.py` —— 核心架构：特征提取 / 决策大脑 / 风控 / 编排 / 回测
- `fu2609_config.py` —— 燃油 2609 主力合约的激进波段配置 + 仓位速查表

## 配置凭据（必读）

**不要把账号密码写进代码**。先在终端里设置环境变量：

### Windows (PowerShell)
```powershell
$env:TQ_USER = "你的快期账号"
$env:TQ_PASS = "你的快期密码"
$env:DEEPSEEK_KEY = "sk-你的DeepSeek密钥"
```

### macOS / Linux
```bash
export TQ_USER="你的快期账号"
export TQ_PASS="你的快期密码"
export DEEPSEEK_KEY="sk-你的DeepSeek密钥"
```

## 申请凭据
- **快期账号**：https://www.shinnytech.com/register-intro/ （TqSdk 母公司，免费）
- **DeepSeek key**：https://platform.deepseek.com/ → 创建 API Key

## 安装依赖
```bash
pip install tqsdk aiohttp numpy
```

## 运行
```bash
# 默认 LIVE=False，跑回测
python tqsdk_deepseek_arch.py

# 看燃油 2609 仓位速查表
python fu2609_config.py
```

⚠ **风险提示**：先在回测和模拟盘里跑通，确认决策逻辑、风控、止损都按预期工作后，再考虑实盘。激进仓位 + 8% 熔断 在涨跌停 15% 的燃油上，单根大 K 线可能造成远超 8% 的回撤。
