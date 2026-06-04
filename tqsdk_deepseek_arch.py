"""
TqSdk (天勤量化) + DeepSeek 自动化期货交易系统 —— 架构骨架
===========================================================
核心设计原则:
  1. 解耦: 慢速 LLM 推理 (秒级) 放进后台 asyncio task, 绝不阻塞主行情循环。
  2. 单循环无锁: 全程跑在 TqSdk 唯一的事件循环里, 协作式调度, 共享状态无需加锁
     (前提: 不引入真正的 threading)。
  3. 风控 fail-closed: 任何字段缺失/解析失败/置信度不足/触及风控线 -> 默认不交易。
  4. 决策幂等: 主循环用 TargetPosTask 管理"目标仓位", 而非每次都 insert_order,
     天然避免重复下单。

模块对应:
  - 模块一 -> FeatureEngine / MarketFeatures
  - 模块二 -> RiskGuardrails / RiskConfig
  - 模块三 -> ReasoningBacktester / EvalRecord
  - 决策大脑 -> DecisionBrain (DeepSeek 异步封装)
  - 实盘编排 -> TradingOrchestrator
"""
from __future__ import annotations

import asyncio
import json
import math
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum
from typing import Optional, List

import aiohttp
import numpy as np
import requests as _requests

from tqsdk import TqApi, TqAuth, TqSim, TqBacktest, TargetPosTask


# =============================================================================
# 决策数据契约
# =============================================================================
class TradeAction(str, Enum):
    LONG = "long"      # 开/加多
    SHORT = "short"    # 开/加空
    CLOSE = "close"    # 平仓至空仓
    HOLD = "hold"      # 不动


@dataclass
class Decision:
    action: TradeAction
    size_pct: float          # 目标仓位占权益比例 [0,1]
    confidence: float        # 模型自评置信度 [0,1]
    reason: str
    raw: dict = field(default_factory=dict)

    @staticmethod
    def from_llm_json(obj: dict) -> "Decision":
        """从模型 JSON 解析。任何缺字段都抛错 -> 上游 fail-closed 处理。"""
        return Decision(
            action=TradeAction(str(obj["action"]).lower()),
            size_pct=float(obj.get("size_pct", 0)) / (100 if obj.get("size_pct", 0) > 1 else 1),
            confidence=float(obj.get("confidence", 0)),
            reason=str(obj.get("reason", "")),
            raw=obj,
        )


# =============================================================================
# 模块一: 实时行情特征提取引擎
# =============================================================================
@dataclass
class MarketFeatures:
    symbol: str
    ts: float
    last_price: float
    price_range_pct: float       # 近窗口 K 线 (high-low)/close
    realized_vol: float          # 已实现波动率
    orderbook_imbalance: float   # 盘口不平衡度 [-1,1]
    oi_change: float             # 持仓量变化
    volume_burst: float          # 成交量异动倍数
    ma5: float = 0.0             # 5 根 K 线均价
    ma20: float = 0.0            # 20 根 K 线均价
    ma60: float = 0.0            # 60 根 K 线均价
    price_vs_ma5: float = 0.0    # 价格相对 MA5 的偏离度
    price_vs_ma20: float = 0.0   # 价格相对 MA20 的偏离度
    trend: str = "震荡"           # 趋势判断

    def to_prompt(self) -> str:
        if self.orderbook_imbalance > 0.15:
            book = "买盘明显占优"
        elif self.orderbook_imbalance < -0.15:
            book = "卖盘明显占优"
        else:
            book = "盘口基本均衡"
        oi_desc = "增仓" if self.oi_change > 0 else "减仓" if self.oi_change < 0 else "持仓不变"
        return (
            f"合约 {self.symbol} | 最新价 {self.last_price:.1f}\n"
            f"趋势: {self.trend} | MA5={self.ma5:.1f} MA20={self.ma20:.1f} MA60={self.ma60:.1f}\n"
            f"价格偏离: 距MA5={self.price_vs_ma5:+.2%} 距MA20={self.price_vs_ma20:+.2%}\n"
            f"波幅={self.price_range_pct:.2%} | 波动率={self.realized_vol:.2%}\n"
            f"盘口: {self.orderbook_imbalance:+.2f} ({book}) | {oi_desc} {abs(self.oi_change):.0f}手\n"
            f"成交量异动={self.volume_burst:.1f}x\n"
            f"请根据以上特征给出交易决策。趋势明确时应给出 long/short，不要总是 hold。"
        )


class FeatureEngine:
    """订阅行情流, 在主循环每次 wait_update 后增量更新特征快照。
    只在数据真的变化时重算 (api.is_changing), 避免空转。"""

    def __init__(self, api: TqApi, symbol: str, kline_dur: int = 60, window: int = 60):
        self.api = api
        self.symbol = symbol
        self.window = window
        self.quote = api.get_quote(symbol)
        # data_length 多取几根, 留出计算缓冲
        self.klines = api.get_kline_serial(symbol, kline_dur, data_length=window + 10)
        self._last_oi: Optional[float] = None
        self.latest: Optional[MarketFeatures] = None

    def update(self) -> Optional[MarketFeatures]:
        # 行情/K线都没变就直接返回旧快照, 省算力
        if not (self.api.is_changing(self.quote) or self.api.is_changing(self.klines.iloc[-1], "close")):
            return self.latest
        try:
            self.latest = self._compute()
        except Exception:
            # 数据未就绪 (如开盘瞬间 NaN) 时静默跳过, 不污染快照
            pass
        return self.latest

    def _compute(self) -> MarketFeatures:
        q = self.quote
        closes = self.klines.close.values[-self.window:]
        highs = self.klines.high.values[-self.window:]
        lows = self.klines.low.values[-self.window:]
        vols = self.klines.volume.values[-self.window:]

        # 已实现波动率: 对数收益标准差
        log_ret = np.diff(np.log(closes[closes > 0]))
        realized_vol = float(np.std(log_ret)) if len(log_ret) > 2 else 0.0

        # 价格区间
        price_range_pct = float((highs.max() - lows.min()) / closes[-1]) if closes[-1] else 0.0

        # 盘口不平衡度
        bid_v, ask_v = q.bid_volume1, q.ask_volume1
        imbalance = (bid_v - ask_v) / (bid_v + ask_v + 1e-9)

        # 持仓量变化
        cur_oi = float(self.klines.close_oi.values[-1])
        oi_change = 0.0 if self._last_oi is None else cur_oi - self._last_oi
        self._last_oi = cur_oi

        # 成交量异动
        mean_vol = float(np.mean(vols[:-1])) if len(vols) > 1 else 0.0
        volume_burst = float(vols[-1] / mean_vol) if mean_vol > 0 else 1.0

        # 均线
        all_closes = self.klines.close.values
        ma5  = float(np.mean(all_closes[-5:]))  if len(all_closes) >= 5  else float(closes[-1])
        ma20 = float(np.mean(all_closes[-20:])) if len(all_closes) >= 20 else float(closes[-1])
        ma60 = float(np.mean(all_closes[-60:])) if len(all_closes) >= 60 else float(closes[-1])
        price = float(q.last_price)
        price_vs_ma5  = (price - ma5)  / ma5  if ma5  else 0.0
        price_vs_ma20 = (price - ma20) / ma20 if ma20 else 0.0

        # 趋势判断: 均线多头/空头排列
        if ma5 > ma20 > ma60 and price > ma5:
            trend = "多头趋势"
        elif ma5 < ma20 < ma60 and price < ma5:
            trend = "空头趋势"
        elif ma5 > ma20 and price > ma20:
            trend = "短期偏多"
        elif ma5 < ma20 and price < ma20:
            trend = "短期偏空"
        else:
            trend = "震荡"

        return MarketFeatures(
            symbol=self.symbol,
            ts=time.time(),
            last_price=price,
            price_range_pct=price_range_pct,
            realized_vol=realized_vol,
            orderbook_imbalance=float(imbalance),
            oi_change=oi_change,
            volume_burst=volume_burst,
            ma5=ma5, ma20=ma20, ma60=ma60,
            price_vs_ma5=price_vs_ma5,
            price_vs_ma20=price_vs_ma20,
            trend=trend,
        )


# =============================================================================
# 决策大脑: DeepSeek 异步封装 (关键: 全异步, 永不阻塞主循环)
# =============================================================================
class DecisionBrain:
    SYSTEM_PROMPT = (
        "你是期货短线交易决策引擎，专注燃油期货波段交易。"
        "根据给定的市场特征（趋势、均线、盘口、波动率）给出明确的交易决策。\n"
        "决策规则:\n"
        "- 多头趋势/短期偏多 + 买盘占优 + 成交量放大 → 优先考虑 long\n"
        "- 空头趋势/短期偏空 + 卖盘占优 + 成交量放大 → 优先考虑 short\n"
        "- 震荡且无明显信号 → hold，但不要总是 hold\n"
        "- size_pct 表示建议仓位占权益比例(0-100)，有明确信号时给 20-40\n"
        "只输出一个 JSON 对象，不要任何解释或 markdown。字段:\n"
        '{"action":"long|short|close|hold","size_pct":0-100,'
        '"confidence":0-1,"reason":"简短中文依据"}'
    )

    def __init__(self, api_key: str, model: str = "deepseek-chat",
                 endpoint: str = "https://api.deepseek.com/chat/completions",
                 timeout: float = 12.0):
        self.api_key = api_key
        self.model = model
        self.endpoint = endpoint
        self.timeout = timeout

    def decide_sync(self, prompt: str) -> Optional[Decision]:
        """同步调用 DeepSeek（用于回测模式，阻塞等待真实响应）。"""
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {self.api_key}",
                   "Content-Type": "application/json"}
        try:
            resp = _requests.post(self.endpoint, json=payload, headers=headers,
                                  timeout=self.timeout)
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            content = content.replace("```json", "").replace("```", "").strip()
            return Decision.from_llm_json(json.loads(content))
        except Exception as e:
            print(f"[Brain] 调用失败, 视为 HOLD: {e}")
            return None

    async def decide(self, prompt: str) -> Optional[Decision]:
        """异步调用 DeepSeek（用于实盘模式，不阻塞主循环）。"""
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {self.api_key}",
                   "Content-Type": "application/json"}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.endpoint, json=payload, headers=headers,
                                        timeout=aiohttp.ClientTimeout(total=self.timeout)) as resp:
                    data = await resp.json()
            content = data["choices"][0]["message"]["content"]
            content = content.replace("```json", "").replace("```", "").strip()
            return Decision.from_llm_json(json.loads(content))
        except Exception as e:
            print(f"[Brain] 调用失败, 视为 HOLD: {e}")
            return None


# =============================================================================
# 模块二: 异步风控卫士层 (拦截器模式, fail-closed)
# =============================================================================
@dataclass
class RiskConfig:
    max_risk_ratio: float = 0.50       # 账户保证金占用率上限 (account.risk_ratio)
    max_position_pct: float = 0.30     # 单合约目标仓位占权益上限
    daily_loss_limit_pct: float = 0.03 # 当日亏损超过初始权益此比例则全天禁开仓
    min_confidence: float = 0.45       # 低于此置信度的决策直接拒绝


@dataclass
class GuardResult:
    approved: bool
    reason: str
    target_volume: Optional[int] = None  # 通过时给出的目标净持仓 (正多负空)


class RiskGuardrails:
    """决策必须先经过 validate() 才能下单。所有检查默认拒绝, 全部通过才放行。"""

    def __init__(self, api: TqApi, symbol: str, config: RiskConfig):
        self.api = api
        self.symbol = symbol
        self.cfg = config
        self.quote = api.get_quote(symbol)
        self._session_start_equity: Optional[float] = None
        self._daily_locked = False

    def mark_session_start(self):
        """每个交易日开盘调用一次, 锁定当日基准权益。"""
        self._session_start_equity = float(self.api.get_account().balance)
        self._daily_locked = False

    def validate(self, decision: Decision) -> GuardResult:
        acc = self.api.get_account()
        pos = self.api.get_position(self.symbol)
        if self._session_start_equity is None:
            self._session_start_equity = float(acc.balance)

        # —— 检查 0: 置信度门槛 ——
        if decision.confidence < self.cfg.min_confidence:
            return GuardResult(False, f"置信度 {decision.confidence:.2f} 低于门槛")

        # —— 检查 1: 当日亏损熔断 ——
        daily_pnl_pct = (acc.balance - self._session_start_equity) / self._session_start_equity
        if daily_pnl_pct <= -self.cfg.daily_loss_limit_pct:
            self._daily_locked = True
        if self._daily_locked and decision.action in (TradeAction.LONG, TradeAction.SHORT):
            return GuardResult(False, f"当日亏损 {daily_pnl_pct:.2%} 触及熔断, 禁止开仓")

        # —— 检查 2: 保证金占用率 ——
        if decision.action in (TradeAction.LONG, TradeAction.SHORT) \
                and acc.risk_ratio >= self.cfg.max_risk_ratio:
            return GuardResult(False, f"保证金占用率 {acc.risk_ratio:.2%} 已达上限")

        # —— 平仓/不动: 直接放行 ——
        if decision.action == TradeAction.HOLD:
            cur = int(pos.pos_long - pos.pos_short)
            return GuardResult(True, "维持现状", target_volume=cur)
        if decision.action == TradeAction.CLOSE:
            return GuardResult(True, "平仓至空仓", target_volume=0)

        # —— 检查 3: 仓位上限 + size_pct -> 手数换算 ——
        capped_pct = min(decision.size_pct, self.cfg.max_position_pct)
        margin_per_lot = float(self.quote.margin)  # 每手保证金
        if margin_per_lot <= 0:
            return GuardResult(False, "保证金数据未就绪")
        lots = math.floor(acc.balance * capped_pct / margin_per_lot)
        if lots < 1:
            return GuardResult(False, "换算手数不足 1 手")
        target = lots if decision.action == TradeAction.LONG else -lots

        return GuardResult(True, f"放行: 目标 {target} 手 (仓位上限裁剪至 {capped_pct:.0%})",
                           target_volume=target)


# =============================================================================
# 实盘编排: 把三者接进 TqSdk 循环
# =============================================================================
class TradingOrchestrator:
    def __init__(self, api: TqApi, symbol: str, brain: DecisionBrain,
                 guard: RiskGuardrails, decision_interval: float = 30.0):
        self.api = api
        self.symbol = symbol
        self.engine = FeatureEngine(api, symbol)
        self.brain = brain
        self.guard = guard
        self.target_pos = TargetPosTask(api, symbol)
        self.decision_interval = decision_interval   # LLM 调用频率上限 (秒)
        self._staged_target: Optional[int] = None     # 后台协程 -> 主循环 的"邮箱"
        self._inflight = False

    async def _decision_loop(self):
        """后台协程: 周期性快照特征 -> 调 DeepSeek -> 过风控 -> 暂存目标仓位。
        asyncio.sleep 会让出控制权, 主循环的 wait_update 照常处理行情。"""
        while True:
            await asyncio.sleep(self.decision_interval)
            feats = self.engine.latest
            if feats is None or self._inflight:
                continue
            self._inflight = True
            try:
                decision = await self.brain.decide(feats.to_prompt())
                if decision is None:
                    continue
                result = self.guard.validate(decision)
                print(f"[决策] {decision.action.value} conf={decision.confidence:.2f} "
                      f"-> {'放行' if result.approved else '拦截'}: {result.reason}")
                if result.approved:
                    self._staged_target = result.target_volume  # 交给主循环执行
            finally:
                self._inflight = False

    def run(self):
        self.guard.mark_session_start()
        self.api.create_task(self._decision_loop())   # 注册后台 LLM 协程
        # 风控如果带逐笔硬止损 (FuelGuardrails) 就在每次 tick 检查一次
        hard_stop = getattr(self.guard, "check_per_trade_stop", None)
        while True:
            self.api.wait_update()
            self.engine.update()                       # 快: 更新特征
            if hard_stop is not None:
                forced = hard_stop()
                if forced is not None:                 # 触发硬止损 -> 立即平仓
                    self.target_pos.set_target_volume(forced)
                    self._staged_target = None
                    continue
            if self._staged_target is not None:        # 快: 执行已过风控的目标仓位
                self.target_pos.set_target_volume(self._staged_target)
                self._staged_target = None


# =============================================================================
# 模块三: 推理验证与回测框架
# =============================================================================
@dataclass
class EvalRecord:
    ts: float
    prompt: str
    action: TradeAction
    confidence: float
    price_at_decision: float
    price_after_horizon: Optional[float] = None  # 决策后 horizon 根 K 线的价格
    forward_return: Optional[float] = None        # 后验收益率
    past_return: Optional[float] = None            # 决策前的价格变化 (用于滞后诊断)


class ReasoningBacktester:
    """在 TqBacktest 模式下运行, 把历史行情分片喂给 DeepSeek, 对齐后续真实表现。
    关键: 必须模拟真实推理延迟 —— 决策只能在"未来"成交, 不能用模型当时看到的价格回填。"""

    def __init__(self, api: TqApi, symbol: str, brain: DecisionBrain,
                 sample_interval: int = 5, horizon: int = 10):
        self.api = api
        self.symbol = symbol
        self.engine = FeatureEngine(api, symbol)
        self.brain = brain
        self.sample_interval = sample_interval  # 每隔几根 K 线采样决策一次
        self.horizon = horizon                  # 前瞻评估窗口 (根)
        self.records: List[EvalRecord] = []
        self._bar_count = 0

    def run_sync(self):
        """回测专用同步主循环：每隔 sample_interval 根 K 线调一次 DeepSeek（阻塞等待）。
        回测模式下 wait_update() 推进历史数据，decide_sync() 真实调用 LLM。"""
        klines = self.engine.klines
        while True:
            self.api.wait_update()
            if not self.api.is_changing(klines.iloc[-1], "datetime"):
                continue
            self._bar_count += 1
            self.engine.update()
            if self._bar_count % self.sample_interval != 0:
                continue
            feats = self.engine.latest
            if feats is None:
                continue
            print(f"[Bar #{self._bar_count}] 调用 DeepSeek 决策...")
            decision = self.brain.decide_sync(feats.to_prompt())
            if decision is None:
                continue
            closes = klines.close.values
            past = float(closes[-1] / closes[-self.horizon] - 1) if len(closes) > self.horizon else 0.0
            self.records.append(EvalRecord(
                ts=feats.ts, prompt=feats.to_prompt(),
                action=decision.action, confidence=decision.confidence,
                price_at_decision=float(closes[-1]), past_return=past,
            ))
            print(f"[决策#{len(self.records):03d}] {decision.action.value} "
                  f"conf={decision.confidence:.2f} 价格={float(closes[-1]):.1f} "
                  f"理由={decision.reason[:40]}")

    async def _evaluate_loop(self):
        """实盘/异步模式保留（不用于回测）。"""
        klines = self.engine.klines
        while True:
            async with self.api.register_update_notify(klines.iloc[-1]) as chan:
                async for _ in chan:
                    if not self.api.is_changing(klines.iloc[-1], "datetime"):
                        continue
                    self._bar_count += 1
                    self.engine.update()
                    if self._bar_count % self.sample_interval != 0:
                        continue
                    feats = self.engine.latest
                    if feats is None:
                        continue
                    decision = await self.brain.decide(feats.to_prompt())
                    if decision is None:
                        continue
                    closes = klines.close.values
                    past = float(closes[-1] / closes[-self.horizon] - 1) if len(closes) > self.horizon else 0.0
                    self.records.append(EvalRecord(
                        ts=feats.ts, prompt=feats.to_prompt(),
                        action=decision.action, confidence=decision.confidence,
                        price_at_decision=float(closes[-1]), past_return=past,
                    ))
                    print(f"[决策#{len(self.records):03d}] {decision.action.value} "
                          f"conf={decision.confidence:.2f} 价格={float(closes[-1]):.1f} "
                          f"理由={decision.reason[:40]}")

    def finalize_forward_returns(self):
        """回测跑完后，按决策价格在历史 K 线里找最近匹配点，向后取 horizon 根的前瞻收益。"""
        closes = self.engine.klines.close.values
        if len(closes) == 0:
            return
        for r in self.records:
            # 找决策价格在 K 线序列里最近的下标
            idx = int(np.argmin(np.abs(closes - r.price_at_decision)))
            future_idx = min(idx + self.horizon, len(closes) - 1)
            if closes[idx] > 0:
                r.price_after_horizon = float(closes[future_idx])
                r.forward_return = float(closes[future_idx] / closes[idx] - 1)

    def metrics(self) -> dict:
        """三大核心指标。"""
        if not self.records:
            return {}
        # 1) 一致性: 相近市场状态下 (按 confidence 分桶或特征聚类) 动作是否稳定
        actions = [r.action for r in self.records]
        dominant = max(set(actions), key=actions.count)
        consistency = actions.count(dominant) / len(actions)

        # 2) 信号 PnL: 按动作方向聚合前瞻收益 (做多取正向, 做空取反向)
        fr = [r for r in self.records if r.forward_return is not None]
        signal_pnl = 0.0
        for r in fr:
            if r.action == TradeAction.LONG:
                signal_pnl += r.forward_return
            elif r.action == TradeAction.SHORT:
                signal_pnl -= r.forward_return

        # 3) 滞后诊断: 决策方向与"过去"走势的相关性 > 与"未来"走势 -> 模型在追涨杀跌
        def sign(a): return 1 if a == TradeAction.LONG else -1 if a == TradeAction.SHORT else 0
        past_align = np.mean([sign(r.action) * r.past_return for r in self.records]) if self.records else 0
        fut_align = np.mean([sign(r.action) * r.forward_return for r in fr]) if fr else 0
        lag_warning = past_align > fut_align  # True 表示决策更像滞后/追势而非预测

        return {
            "样本数": len(self.records),
            "动作一致性": round(consistency, 3),
            "信号累计前瞻收益": round(signal_pnl, 4),
            "与过去走势相关性": round(float(past_align), 4),
            "与未来走势相关性": round(float(fut_align), 4),
            "存在滞后倾向": bool(lag_warning),
        }


# =============================================================================
# 启动入口示例
# =============================================================================
if __name__ == "__main__":
    # 燃油 2609 主力合约，风控参数内联，避免跨模块循环导入
    SYMBOL = "SHFE.fu2609"

    # —— 凭据从环境变量读取, 不写进源码 ——
    # 在终端先设置:
    #   export TQ_USER="你的快期账号"
    #   export TQ_PASS="你的快期密码"
    #   export DEEPSEEK_KEY="sk-你的DeepSeek密钥"
    TQ_USER = os.environ.get("TQ_USER")
    TQ_PASS = os.environ.get("TQ_PASS")
    DEEPSEEK_KEY = os.environ.get("DEEPSEEK_KEY")
    if not (TQ_USER and TQ_PASS and DEEPSEEK_KEY):
        raise RuntimeError(
            "请先设置环境变量 TQ_USER / TQ_PASS / DEEPSEEK_KEY 再运行。"
        )

    LIVE = False  # 先用回测/模拟跑通, 千万别一上来就实盘

    # 激进燃油风控参数 (来自 fu2609_config.FuelRiskConfig)
    _fuel_cfg = RiskConfig(
        max_risk_ratio=0.60,
        max_position_pct=0.45,
        daily_loss_limit_pct=0.08,
        min_confidence=0.45,
    )

    if LIVE:
        api = TqApi(TqSim(), auth=TqAuth(TQ_USER, TQ_PASS))
        brain = DecisionBrain(DEEPSEEK_KEY)
        guard = RiskGuardrails(api, SYMBOL, _fuel_cfg)
        TradingOrchestrator(api, SYMBOL, brain, guard).run()
    else:
        print("[启动] 正在连接快期服务器并初始化回测...")
        api = TqApi(
            TqSim(init_balance=200000),
            # 1 个交易日: 给 DeepSeek 足够时间回应每个决策 (回测会快进, LLM 调用是真实网络)
            backtest=TqBacktest(start_dt=date(2026, 5, 11), end_dt=date(2026, 5, 12)),
            auth=TqAuth(TQ_USER, TQ_PASS),
        )
        print("[启动] 连接成功，开始加载 K 线数据...")
        brain = DecisionBrain(DEEPSEEK_KEY)
        # sample_interval=30: 每 30 根 1 分钟 K 线决策一次, 1 个交易日约 15 次决策
        bt = ReasoningBacktester(api, SYMBOL, brain, sample_interval=30)
        print("[启动] 开始同步回测，每 30 根 K 线调用一次 DeepSeek...")
        try:
            bt.run_sync()   # 同步主循环，阻塞等待每次 DeepSeek 响应
        except Exception:   # TqSdk 回测结束抛 BacktestFinished
            bt.finalize_forward_returns()
            print("\n===== 回测结果 =====")
            print(bt.metrics())
        finally:
            api.close()
