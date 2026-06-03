"""
行情模拟器 - 生成模拟 CTP tick 数据
对应原项目: src/trade-core/market/ctp_market.cpp (行情接入层)
"""
import random
import math
from datetime import datetime, timedelta
from data_struct import MarketData, eTapeDir


class MarketSimulator:
    """
    模拟期货合约的 tick 行情, 使用布朗运动 + 趋势叠加
    """
    def __init__(self, contract: str, base_price: float,
                 price_tick: float = 1.0, volatility: float = 0.002):
        self.contract = contract
        self.price_tick = price_tick
        self.volatility = volatility

        self._price = base_price
        self._open = base_price
        self._high = base_price
        self._low = base_price
        self._volume = 0
        self._open_interest = 50000.0
        self._trend = 0.0
        self._trend_duration = 0
        self._tick_index = 0
        self._start_time = datetime(2024, 11, 1, 9, 0, 0)

    def next_tick(self) -> MarketData:
        self._tick_index += 1

        # 趋势切换
        if self._trend_duration <= 0:
            self._trend = random.gauss(0, self.volatility * 0.5)
            self._trend_duration = random.randint(10, 60)
        self._trend_duration -= 1

        # 价格变动 (布朗运动 + 趋势)
        shock = random.gauss(self._trend, self.volatility)
        new_price = self._price * (1 + shock)
        new_price = round(new_price / self.price_tick) * self.price_tick
        new_price = max(new_price, self.price_tick)

        direction = eTapeDir.Up if new_price > self._price else (
            eTapeDir.Down if new_price < self._price else eTapeDir.Flat)
        self._price = new_price

        self._high = max(self._high, new_price)
        self._low  = min(self._low,  new_price)

        last_vol = random.randint(1, 50)
        self._volume += last_vol
        oi_change = random.gauss(0, 5)
        self._open_interest += oi_change

        spread = self.price_tick
        tick_time = self._start_time + timedelta(seconds=self._tick_index * 0.5)

        md = MarketData(
            instrument_id        = self.contract,
            update_time          = tick_time.strftime("%H:%M:%S"),
            update_millisec      = random.randint(0, 999),
            pre_close_price      = self._open,
            pre_settlement_price = self._open,
            last_price           = new_price,
            volume               = self._volume,
            last_volume          = last_vol,
            open_interest        = self._open_interest,
            last_open_interest   = oi_change,
            open_price           = self._open,
            highest_price        = self._high,
            lowest_price         = self._low,
            upper_limit_price    = self._open * 1.05,
            lower_limit_price    = self._open * 0.95,
            average_price        = (self._open + new_price) / 2,
            tape_dir             = direction,
        )
        # 五档盘口
        for i in range(5):
            md.bid_price[i]  = new_price - (i + 1) * spread
            md.bid_volume[i] = random.randint(10, 200)
            md.ask_price[i]  = new_price + (i + 1) * spread
            md.ask_volume[i] = random.randint(10, 200)

        return md
