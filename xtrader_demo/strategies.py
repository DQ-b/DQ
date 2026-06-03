"""
X-Trader 策略实现 (Python 模拟版)
实现原项目 src/strategy/ 中的两个策略逻辑骨架:
  1. high_low  - 日内高低价突破策略
  2. decline_scalping - 下降趋势套利
"""
import sys
from typing import Optional
from data_struct import MarketData, Order, eOrderFlag, eOrderStatus, eDirOffset
from strategy_base import Strategy


# ─────────────────────────────────────────────
# 策略1: 高低价突破 (high_low)
# 对应: src/strategy/high_low.h / high_low.cpp
# ─────────────────────────────────────────────
class HighLowStrategy(Strategy):
    """
    逻辑: 跟踪日内最高/最低价, 当价格突破最高价+open_point时买开,
          突破最低价-open_point时卖开; 持仓后达到close_point平仓
          或触发stop_loss止损
    """
    def __init__(self, strat_id, frame, contract: str):
        super().__init__(strat_id, frame)
        self.contracts.add(contract)
        self._contract = contract
        self._buy_ref: Optional[int] = None
        self._sell_ref: Optional[int] = None

        self.tmp_high: float = 0.0
        self.tmp_low: float = float("inf")
        self.open_point: float = 2.0    # 突破点数
        self.close_point: float = 1.0   # 止盈点数
        self.stop_loss: float = 1.5     # 止损点数
        self.max_loss_count: int = 3
        self.buy_loss: int = 0
        self.sell_loss: int = 0
        self._once_vol: int = 1
        self._is_closing: bool = False
        self._open_price: float = 0.0

    def on_init(self):
        self.frame._log(f"[策略] HighLow 初始化 合约={self._contract}")

    def on_tick(self, tick: MarketData):
        price = tick.last_price
        pos = self.get_position(self._contract)

        # 更新日内高低
        if price > self.tmp_high:
            self.tmp_high = price
        if price < self.tmp_low:
            self.tmp_low = price

        long_pos = pos.long_.position
        short_pos = pos.short_.position

        # 无持仓时寻找开仓机会
        if long_pos == 0 and short_pos == 0 and not self._is_closing:
            # 突破高点买开
            if (self._buy_ref is None and
                    self.buy_loss < self.max_loss_count and
                    price > self.tmp_high + self.open_point):
                self._open_price = price
                self._buy_ref = self.buy_open(
                    eOrderFlag.Limit, self._contract,
                    tick.ask_price[0], self._once_vol)
            # 突破低点卖开
            elif (self._sell_ref is None and
                  self.sell_loss < self.max_loss_count and
                  price < self.tmp_low - self.open_point):
                self._open_price = price
                self._sell_ref = self.sell_open(
                    eOrderFlag.Limit, self._contract,
                    tick.bid_price[0], self._once_vol)

        # 持多仓: 止盈/止损
        elif long_pos > 0:
            pnl = price - self._open_price
            if pnl >= self.close_point:
                self._is_closing = True
                self.sell_close(eOrderFlag.Limit, self._contract,
                                tick.bid_price[0], long_pos)
            elif pnl <= -self.stop_loss:
                self._is_closing = True
                self.buy_loss += 1
                self.sell_close(eOrderFlag.Market, self._contract,
                                0, long_pos)

        # 持空仓: 止盈/止损
        elif short_pos > 0:
            pnl = self._open_price - price
            if pnl >= self.close_point:
                self._is_closing = True
                self.buy_close(eOrderFlag.Limit, self._contract,
                               tick.ask_price[0], short_pos)
            elif pnl <= -self.stop_loss:
                self._is_closing = True
                self.sell_loss += 1
                self.buy_close(eOrderFlag.Market, self._contract,
                               0, short_pos)

    def on_trade(self, order: Order):
        if order.dir_offset in (eDirOffset.SellClose, eDirOffset.BuyClose,
                                 eDirOffset.SellCloseToday, eDirOffset.BuyCloseToday):
            self._is_closing = False
            self._buy_ref = None
            self._sell_ref = None

    def on_cancel(self, order: Order):
        if order.order_ref == self._buy_ref:
            self._buy_ref = None
        if order.order_ref == self._sell_ref:
            self._sell_ref = None


# ─────────────────────────────────────────────
# 策略2: 下降趋势套利 (decline_scalping)
# 对应: src/strategy/decline_scalping.h
# ─────────────────────────────────────────────
class DeclineScalpingStrategy(Strategy):
    """
    逻辑: 监测连续下跌行情, 在跌幅达到阈值时做多反弹
    """
    def __init__(self, strat_id, frame, contract: str):
        super().__init__(strat_id, frame)
        self.contracts.add(contract)
        self._contract = contract
        self._decline_threshold: float = 3.0   # 跌幅阈值(点)
        self._profit_target: float = 1.5
        self._stop_loss: float = 2.0
        self._peak_price: float = 0.0
        self._entry_price: float = 0.0
        self._in_position: bool = False
        self._tick_count: int = 0

    def on_init(self):
        self.frame._log(f"[策略] DeclineScalping 初始化 合约={self._contract}")

    def on_tick(self, tick: MarketData):
        price = tick.last_price
        self._tick_count += 1

        if self._peak_price == 0:
            self._peak_price = price
            return

        if price > self._peak_price:
            self._peak_price = price

        pos = self.get_position(self._contract)
        long_pos = pos.long_.position

        decline = self._peak_price - price

        if not self._in_position and long_pos == 0:
            if decline >= self._decline_threshold:
                self._entry_price = price
                self._in_position = True
                self.buy_open(eOrderFlag.Limit, self._contract,
                              tick.ask_price[0], 1)
        elif long_pos > 0:
            pnl = price - self._entry_price
            if pnl >= self._profit_target:
                self._in_position = False
                self._peak_price = price
                self.sell_close(eOrderFlag.Limit, self._contract,
                                tick.bid_price[0], long_pos)
            elif pnl <= -self._stop_loss:
                self._in_position = False
                self._peak_price = price
                self.sell_close(eOrderFlag.Market, self._contract, 0, long_pos)

    def on_trade(self, order: Order):
        if order.dir_offset in (eDirOffset.SellClose, eDirOffset.SellCloseToday):
            self._in_position = False
