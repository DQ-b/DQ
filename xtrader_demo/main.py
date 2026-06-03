"""
X-Trader Demo - 终端演示主程序
模拟: 行情接收 → 策略运算 → 委托/成交 → 持仓统计
"""
import sys
import time
import random
from collections import deque

from data_struct import eTapeDir
from frame import Frame
from market_simulator import MarketSimulator
from strategies import HighLowStrategy, DeclineScalpingStrategy

# ── ANSI 颜色 ──────────────────────────────────
RED    = "\033[91m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"
CLEAR  = "\033[2J\033[H"

TOTAL_TICKS = 120
LOG_LINES   = 8

log_buffer: deque = deque(maxlen=LOG_LINES)
trade_stats = {"buy_open": 0, "sell_open": 0, "trades": 0, "pnl": 0.0}


def colored_log(msg: str):
    if "[成交]" in msg:
        log_buffer.append(f"{GREEN}{msg}{RESET}")
        trade_stats["trades"] += 1
    elif "[委托]" in msg:
        log_buffer.append(f"{YELLOW}{msg}{RESET}")
        if "买开" in msg:
            trade_stats["buy_open"] += 1
        elif "卖开" in msg:
            trade_stats["sell_open"] += 1
    elif "[撤单]" in msg:
        log_buffer.append(f"{DIM}{msg}{RESET}")
    elif "[策略]" in msg:
        log_buffer.append(f"{CYAN}{msg}{RESET}")
    else:
        log_buffer.append(msg)


def render(tick, frame: Frame, sim: MarketSimulator,
           strat1: HighLowStrategy, strat2: DeclineScalpingStrategy,
           tick_num: int):
    print(CLEAR, end="")

    # ── 标题栏 ─────────────────────────────────
    print(f"{BOLD}{CYAN}{'─'*64}")
    print(f"  X-Trader  量化交易框架演示  (Python 模拟版)")
    print(f"  对应项目: https://github.com/QuantLaboratory/X-Trader")
    print(f"{'─'*64}{RESET}")

    # ── 实时行情 ───────────────────────────────
    p = tick.last_price
    prev_p = p - random.uniform(-0.5, 0.5)  # 近似上一价
    chg = p - tick.pre_close_price
    chg_pct = chg / tick.pre_close_price * 100
    color = RED if chg >= 0 else GREEN
    arrow = "▲" if tick.tape_dir == eTapeDir.Up else (
            "▼" if tick.tape_dir == eTapeDir.Down else "─")

    print(f"\n{BOLD}  [ 行情 ]  {tick.instrument_id}  "
          f"{color}{p:.1f}  {arrow}  {chg:+.1f} ({chg_pct:+.2f}%){RESET}")
    print(f"  时间: {tick.update_time}.{tick.update_millisec:03d}   "
          f"成交量: {tick.volume:,}   持仓: {tick.open_interest:.0f}")
    print(f"  今开: {tick.open_price:.1f}  最高: {tick.highest_price:.1f}  "
          f"最低: {tick.lowest_price:.1f}  涨停: {tick.upper_limit_price:.1f}  "
          f"跌停: {tick.lower_limit_price:.1f}")

    # ── 五档盘口 ───────────────────────────────
    print(f"\n  {'─'*36}")
    print(f"  {'卖档':>4}  {'价格':>8}  {'数量':>8}")
    print(f"  {'─'*36}")
    for i in range(4, -1, -1):
        print(f"  {f'卖{i+1}':>4}  {RED}{tick.ask_price[i]:>8.1f}{RESET}  "
              f"{tick.ask_volume[i]:>8,}")
    print(f"  {'─'*36}")
    for i in range(5):
        print(f"  {f'买{i+1}':>4}  {GREEN}{tick.bid_price[i]:>8.1f}{RESET}  "
              f"{tick.bid_volume[i]:>8,}")
    print(f"  {'─'*36}")

    # ── 持仓 ───────────────────────────────────
    print(f"\n{BOLD}  [ 持仓 ]{RESET}")
    for contract, pos in frame._positions.items():
        lp = pos.long_.position
        sp = pos.short_.position
        lc = pos.long_.avg_open_cost
        sc = pos.short_.avg_open_cost
        lf = (p - lc) * lp if lp > 0 else 0
        sf = (sc - p) * sp if sp > 0 else 0
        if lp > 0:
            pnl_color = GREEN if lf >= 0 else RED
            print(f"  {contract}  多头: {lp}手  均价: {lc:.1f}  "
                  f"浮盈: {pnl_color}{lf:+.1f}{RESET}")
        if sp > 0:
            pnl_color = GREEN if sf >= 0 else RED
            print(f"  {contract}  空头: {sp}手  均价: {sc:.1f}  "
                  f"浮盈: {pnl_color}{sf:+.1f}{RESET}")
        if lp == 0 and sp == 0:
            print(f"  {contract}  空仓")

    # ── 策略状态 ───────────────────────────────
    print(f"\n{BOLD}  [ 策略状态 ]{RESET}")
    print(f"  HighLow:       日高={strat1.tmp_high:.1f}  日低={strat1.tmp_low:.1f}  "
          f"买损次={strat1.buy_loss}  卖损次={strat1.sell_loss}")
    print(f"  DeclineScalp:  峰值={strat2._peak_price:.1f}  "
          f"跌幅={strat2._peak_price - p:.1f}  "
          f"持仓={'是' if strat2._in_position else '否'}")

    # ── 统计 ───────────────────────────────────
    total_orders = len(frame._orders)
    print(f"\n  委托总数: {total_orders}   成交: {trade_stats['trades']}   "
          f"买开: {trade_stats['buy_open']}   卖开: {trade_stats['sell_open']}")

    # ── 进度条 ─────────────────────────────────
    pct = tick_num / TOTAL_TICKS
    bar_len = 40
    filled = int(bar_len * pct)
    bar = "█" * filled + "░" * (bar_len - filled)
    print(f"\n  进度  [{bar}] {tick_num}/{TOTAL_TICKS}")

    # ── 日志 ───────────────────────────────────
    print(f"\n{BOLD}  [ 事件日志 ]{RESET}")
    for line in log_buffer:
        print(f"  {line}")

    print(f"\n{DIM}  按 Ctrl+C 退出{RESET}")
    sys.stdout.flush()


def main():
    random.seed(42)

    # 创建框架
    frame = Frame(logger=colored_log)

    # 行情模拟器: 沪铜主力 CU2411
    sim = MarketSimulator(
        contract="CU2411",
        base_price=76000.0,
        price_tick=10.0,
        volatility=0.003,
    )

    # 注册策略
    strat1 = HighLowStrategy(1, frame, "CU2411")
    strat1.open_point  = 30.0
    strat1.close_point = 20.0
    strat1.stop_loss   = 40.0

    strat2 = DeclineScalpingStrategy(2, frame, "CU2411")
    strat2._decline_threshold = 50.0
    strat2._profit_target     = 20.0
    strat2._stop_loss         = 40.0

    frame.add_strategy(strat1)
    frame.add_strategy(strat2)

    print(f"{CLEAR}{BOLD}{CYAN}X-Trader 演示启动中...{RESET}\n")
    time.sleep(1)

    # 主循环: 模拟 tick 驱动
    for i in range(1, TOTAL_TICKS + 1):
        tick = sim.next_tick()
        frame.on_tick(tick)
        render(tick, frame, sim, strat1, strat2, i)
        time.sleep(0.3)

    # 最终结果
    print(f"\n{BOLD}{GREEN}{'─'*64}")
    print("  演示结束 - 最终持仓")
    print(f"{'─'*64}{RESET}")
    for contract, pos in frame._positions.items():
        print(f"  {contract}: 多={pos.long_.position}手  空={pos.short_.position}手")
    print(f"  委托总数: {len(frame._orders)}  成交笔数: {trade_stats['trades']}")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{YELLOW}用户中断{RESET}\n")
