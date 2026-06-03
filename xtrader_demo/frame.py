"""
X-Trader 核心框架 (Python 模拟版)
对应原项目: src/framework/frame.cpp
负责: 策略注册、行情分发、订单管理、持仓管理
"""
import time
from datetime import datetime
from typing import Dict, List, Optional, Callable
from data_struct import (
    MarketData, Order, Position, PosiDetail,
    eDirOffset, eOrderFlag, eOrderStatus, eEventFlag
)

_ref = 0

def _next_ref() -> int:
    global _ref
    _ref += 1
    return _ref


class Frame:
    def __init__(self, logger: Optional[Callable] = None):
        self._strategies = {}        # strat_id -> Strategy
        self._positions: Dict[str, Position] = {}
        self._orders: Dict[int, Order] = {}
        self._log = logger or print
        self._match_delay = 0.05     # 模拟撮合延迟(秒)

    # ---------- 策略注册 ----------
    def add_strategy(self, strategy) -> None:
        self._strategies[strategy.strat_id] = strategy
        strategy.on_init()

    # ---------- 行情分发 ----------
    def on_tick(self, tick: MarketData) -> None:
        for strat in self._strategies.values():
            if tick.instrument_id in strat.contracts:
                strat.on_tick(tick)
                # 触发挂单撮合检查
                self._try_match_pending(tick)

    # ---------- 下单 ----------
    def insert_order(self, strat_id: int, contract: str,
                     dir_offset: eDirOffset, order_flag: eOrderFlag,
                     price: float, volume: int) -> int:
        ref = _next_ref()
        order = Order(
            order_ref=ref,
            event_flag=eEventFlag.Order,
            instrument_id=contract,
            dir_offset=dir_offset,
            order_flag=order_flag,
            limit_price=price,
            volume_total_original=volume,
            volume_total=volume,
            order_status=eOrderStatus.NoTradeQueueing,
            insert_time=datetime.now().strftime("%H:%M:%S.%f")[:-3],
        )
        self._orders[ref] = order
        strat = self._strategies.get(strat_id)
        if strat:
            strat.on_order(order)
        self._log(f"  [委托] #{ref} {contract} {dir_offset.value} {order_flag.value} "
                  f"价格={price:.1f} 手数={volume}")
        return ref

    # ---------- 撤单 ----------
    def cancel_order(self, order_ref: int) -> bool:
        order = self._orders.get(order_ref)
        if order and order.order_status == eOrderStatus.NoTradeQueueing:
            order.order_status = eOrderStatus.Canceled
            order.event_flag = eEventFlag.Cancel
            self._dispatch_order_event(order)
            self._log(f"  [撤单] #{order_ref} {order.instrument_id} 已撤销")
            return True
        return False

    # ---------- 模拟撮合 ----------
    def _try_match_pending(self, tick: MarketData) -> None:
        for ref, order in list(self._orders.items()):
            if order.order_status != eOrderStatus.NoTradeQueueing:
                continue
            matched = False
            if order.dir_offset in (eDirOffset.BuyOpen, eDirOffset.BuyClose,
                                     eDirOffset.BuyCloseToday, eDirOffset.BuyCloseYesterday):
                matched = (order.order_flag == eOrderFlag.Market or
                           tick.ask_price[0] <= order.limit_price)
                fill_price = tick.ask_price[0]
            else:
                matched = (order.order_flag == eOrderFlag.Market or
                           tick.bid_price[0] >= order.limit_price)
                fill_price = tick.bid_price[0]

            if matched:
                order.volume_traded = order.volume_total_original
                order.volume_total = 0
                order.order_status = eOrderStatus.AllTraded
                order.event_flag = eEventFlag.Trade
                self._update_position(order, fill_price)
                self._dispatch_order_event(order)
                self._log(f"  [成交] #{ref} {order.instrument_id} {order.dir_offset.value} "
                          f"成交价={fill_price:.1f} 手数={order.volume_traded}")

    def _update_position(self, order: Order, fill_price: float) -> None:
        contract = order.instrument_id
        if contract not in self._positions:
            self._positions[contract] = Position(id=contract)
        pos = self._positions[contract]
        vol = order.volume_traded
        if order.dir_offset == eDirOffset.BuyOpen:
            pos.long_.position += vol
            pos.long_.today_position += vol
            pos.long_.closeable += vol
            n = pos.long_.position
            old_cost = pos.long_.avg_open_cost * (n - vol)
            pos.long_.avg_open_cost = (old_cost + fill_price * vol) / n
        elif order.dir_offset == eDirOffset.SellOpen:
            pos.short_.position += vol
            pos.short_.today_position += vol
            pos.short_.closeable += vol
            n = pos.short_.position
            old_cost = pos.short_.avg_open_cost * (n - vol)
            pos.short_.avg_open_cost = (old_cost + fill_price * vol) / n
        elif order.dir_offset in (eDirOffset.SellClose, eDirOffset.SellCloseToday, eDirOffset.SellCloseYesterday):
            pos.long_.position = max(0, pos.long_.position - vol)
            pos.long_.closeable = max(0, pos.long_.closeable - vol)
        elif order.dir_offset in (eDirOffset.BuyClose, eDirOffset.BuyCloseToday, eDirOffset.BuyCloseYesterday):
            pos.short_.position = max(0, pos.short_.position - vol)
            pos.short_.closeable = max(0, pos.short_.closeable - vol)

    def _dispatch_order_event(self, order: Order) -> None:
        for strat in self._strategies.values():
            if order.instrument_id in strat.contracts:
                if order.event_flag == eEventFlag.Trade:
                    strat.on_trade(order)
                elif order.event_flag == eEventFlag.Cancel:
                    strat.on_cancel(order)
                elif order.event_flag == eEventFlag.ErrorInsert:
                    strat.on_error(order)

    def get_position(self, contract: str) -> Position:
        return self._positions.get(contract, Position(id=contract))

    def get_order(self, ref: int) -> Optional[Order]:
        return self._orders.get(ref)
