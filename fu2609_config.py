"""
燃油 2609 主力 (SHFE.fu2609) 专用配置
=====================================
合约规格 (2026, 来自上期所):
  - 合约乘数 volume_multiple = 10 吨/手
  - 最小变动价位 0.01... 实际燃油是 1 元/吨 -> 一跳 = 10 元/手
  - 交易所一般持仓保证金比例 ~17% (期货公司实收常 18~20%)
  - 涨跌停板 15% (高波动!)

用户选择: 波段节奏 / 激进仓位 / 8% 日内熔断

风险提示 (务必理解):
  激进仓位(40%权益≈4倍名义杠杆) + 8%熔断, 在涨跌停15%的燃油上,
  单根大K线可能在熔断触发前就造成远超8%的回撤。日内熔断是"事后止损",
  真正的事前保护是 [单笔仓位上限] + [逐笔浮亏硬止损]。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional
import math

if TYPE_CHECKING:
    from tqsdk import TqApi

SYMBOL = "SHFE.fu2609"


@dataclass
class FuelRiskConfig:
    """独立配置类，不依赖 tqsdk_deepseek_arch，避免循环导入。"""
    max_risk_ratio: float = 0.60        # 账户总保证金占用率上限
    max_position_pct: float = 0.45      # 激进: 单笔目标仓位上限 45% 权益
    daily_loss_limit_pct: float = 0.08  # 当日亏损 8% 全天禁开仓
    min_confidence: float = 0.65        # 高仓位 -> 提高置信度门槛
    per_trade_stop_pct: float = 0.40    # 单笔浮亏达保证金 40% 即强平


class FuelGuardrails:
    """燃油专用风控：继承 RiskGuardrails 逻辑 + 逐笔浮亏硬止损。
    延迟导入 tqsdk_deepseek_arch 避免循环引用。"""

    def __init__(self, api: "TqApi", symbol: str = SYMBOL,
                 config: Optional[FuelRiskConfig] = None):
        # 延迟导入，此时 tqsdk_deepseek_arch 已完全加载
        from tqsdk_deepseek_arch import RiskConfig, RiskGuardrails

        self.cfg = config or FuelRiskConfig()
        # 将 FuelRiskConfig 字段映射到 RiskConfig，复用 validate()
        base_cfg = RiskConfig(
            max_risk_ratio=self.cfg.max_risk_ratio,
            max_position_pct=self.cfg.max_position_pct,
            daily_loss_limit_pct=self.cfg.daily_loss_limit_pct,
            min_confidence=self.cfg.min_confidence,
        )
        self._inner = RiskGuardrails(api, symbol, base_cfg)
        self.api = api
        self.symbol = symbol
        self.quote = api.get_quote(symbol)

    # 代理 RiskGuardrails 的公共接口
    def mark_session_start(self):
        self._inner.mark_session_start()

    def validate(self, decision):
        return self._inner.validate(decision)

    def lots_from_pct(self, size_pct: float) -> int:
        acc = self.api.get_account()
        margin_per_lot = float(self.quote.margin)
        if margin_per_lot <= 0:
            return 0
        capped = min(size_pct, self.cfg.max_position_pct)
        return math.floor(acc.balance * capped / margin_per_lot)

    def check_per_trade_stop(self) -> Optional[int]:
        """每次主循环调用: 检查当前持仓浮亏是否触及硬止损。
        返回 0 表示需强平; None 表示无需动作。"""
        pos = self.api.get_position(self.symbol)
        net = int(pos.pos_long - pos.pos_short)
        if net == 0:
            return None
        float_profit = float(pos.float_profit_long + pos.float_profit_short)
        occupied_margin = float(self.quote.margin) * abs(net)
        if occupied_margin <= 0:
            return None
        if float_profit < -self.cfg.per_trade_stop_pct * occupied_margin:
            return 0
        return None


# =============================================================================
# 针对你的资金量的仓位速查表 (单手保证金按实收 18% 估)
# =============================================================================
def position_table(balance: float, price: float = 3000.0,
                   margin_rate: float = 0.18) -> str:
    vm = 10
    margin_per_lot = price * vm * margin_rate
    rows = []
    for pct in (0.30, 0.40, 0.50):
        lots = math.floor(balance * pct / margin_per_lot)
        notional = lots * vm * price
        leverage = notional / balance if balance else 0
        rows.append(f"  仓位{pct:.0%}: {lots:>3d}手  名义市值≈{notional:>10,.0f}元  杠杆≈{leverage:.1f}x")
    return (f"资金 {balance:,.0f} 元 @ 价格 {price} / 单手保证金≈{margin_per_lot:,.0f}元\n"
            + "\n".join(rows))


if __name__ == "__main__":
    print(position_table(balance=50000))
    print(position_table(balance=100000))
