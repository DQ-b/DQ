"""
X-Trader 核心数据结构 (Python 模拟版)
对应原项目: src/include/data_struct.h
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class eTapeDir(Enum):
    Up   =  1
    Flat =  0
    Down = -1


class eDirOffset(Enum):
    BuyOpen            = "买开"
    SellOpen           = "卖开"
    BuyClose           = "买平"
    SellClose          = "卖平"
    BuyCloseToday      = "买平今"
    SellCloseToday     = "卖平今"
    BuyCloseYesterday  = "买平昨"
    SellCloseYesterday = "卖平昨"


class eOrderFlag(Enum):
    Limit  = "限价"
    Market = "市价"
    FOK    = "FOK"
    FAK    = "FAK"


class eOrderStatus(Enum):
    AllTraded            = "全部成交"
    PartTradedQueueing   = "部分成交"
    NoTradeQueueing      = "未成交排队"
    Canceled             = "已撤单"
    Unknown              = "未知"


class eEventFlag(Enum):
    Order       = "委托"
    Trade       = "成交"
    Cancel      = "撤单"
    ErrorInsert = "报单错误"
    ErrorCancel = "撤单错误"


@dataclass
class MarketData:
    instrument_id: str = ""
    update_time: str = ""
    update_millisec: int = 0

    pre_close_price: float = 0.0
    pre_settlement_price: float = 0.0
    last_price: float = 0.0
    volume: int = 0
    last_volume: int = 0
    open_interest: float = 0.0
    last_open_interest: float = 0.0

    open_price: float = 0.0
    highest_price: float = 0.0
    lowest_price: float = 0.0
    upper_limit_price: float = 0.0
    lower_limit_price: float = 0.0
    settlement_price: float = 0.0

    bid_price: List[float] = field(default_factory=lambda: [0.0]*5)
    bid_volume: List[int]  = field(default_factory=lambda: [0]*5)
    ask_price: List[float] = field(default_factory=lambda: [0.0]*5)
    ask_volume: List[int]  = field(default_factory=lambda: [0]*5)

    average_price: float = 0.0
    tape_dir: eTapeDir = eTapeDir.Flat


@dataclass
class Order:
    order_ref: int = 0
    event_flag: eEventFlag = eEventFlag.Order
    instrument_id: str = ""
    dir_offset: eDirOffset = eDirOffset.BuyOpen
    order_flag: eOrderFlag = eOrderFlag.Limit
    limit_price: float = 0.0
    volume_total_original: int = 0
    volume_traded: int = 0
    volume_total: int = 0
    order_status: eOrderStatus = eOrderStatus.Unknown
    insert_time: str = ""
    error_msg: str = ""


@dataclass
class PosiDetail:
    position: int = 0
    today_position: int = 0
    his_position: int = 0
    closeable: int = 0
    avg_open_cost: float = 0.0


@dataclass
class Position:
    id: str = ""
    long_: PosiDetail = field(default_factory=PosiDetail)
    short_: PosiDetail = field(default_factory=PosiDetail)


@dataclass
class Sample:
    """K线 Bar"""
    id: str = ""
    period: int = 60
    time: str = ""
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: int = 0
    delta: int = 0
    poc: float = 0.0
    is_new: bool = True
    price_tick: float = 1.0
    active_buy_volume: Dict[float, int] = field(default_factory=dict)
    active_sell_volume: Dict[float, int] = field(default_factory=dict)
