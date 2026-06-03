"""
X-Trader 策略基类 (Python 模拟版)
对应原项目: src/include/strategy.h  +  src/framework/strategy.cpp
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Set
from data_struct import MarketData, Order, Position, eDirOffset, eOrderFlag

if TYPE_CHECKING:
    from frame import Frame

_orderref_counter = 0


def _next_ref() -> int:
    global _orderref_counter
    _orderref_counter += 1
    return _orderref_counter


class Strategy:
    def __init__(self, strat_id: int, frame: "Frame"):
        self._id = strat_id
        self._frame = frame
        self._contracts: Set[str] = set()

    # ---------- 生命周期回调 ----------
    def on_init(self): pass
    def on_tick(self, tick: MarketData): pass
    def on_order(self, order: Order): pass
    def on_trade(self, order: Order): pass
    def on_cancel(self, order: Order): pass
    def on_error(self, order: Order): pass
    def on_update(self): pass

    # ---------- 属性 ----------
    @property
    def strat_id(self) -> int:
        return self._id

    @property
    def frame(self) -> "Frame":
        return self._frame

    @property
    def contracts(self) -> Set[str]:
        return self._contracts

    # ---------- 下单接口 ----------
    def buy_open(self, flag: eOrderFlag, contract: str, price: float, volume: int) -> int:
        return self._frame.insert_order(self._id, contract, eDirOffset.BuyOpen, flag, price, volume)

    def sell_open(self, flag: eOrderFlag, contract: str, price: float, volume: int) -> int:
        return self._frame.insert_order(self._id, contract, eDirOffset.SellOpen, flag, price, volume)

    def buy_close(self, flag: eOrderFlag, contract: str, price: float, volume: int) -> int:
        return self._frame.insert_order(self._id, contract, eDirOffset.BuyClose, flag, price, volume)

    def sell_close(self, flag: eOrderFlag, contract: str, price: float, volume: int) -> int:
        return self._frame.insert_order(self._id, contract, eDirOffset.SellClose, flag, price, volume)

    def cancel_order(self, order_ref: int) -> bool:
        return self._frame.cancel_order(order_ref)

    def get_position(self, contract: str) -> Position:
        return self._frame.get_position(contract)
