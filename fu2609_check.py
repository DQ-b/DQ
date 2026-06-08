# -*- coding: utf-8 -*-
"""
FU2609 fuel-oil futures signal checker.

This is a local decision-support script only. It does not place orders and its
"consistency" score is indicator agreement, not a probability forecast.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


SYMBOL = "FU2609"
DEEPSEEK_BASE_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-v4-flash"


def fetch_text(url: str, timeout: int = 5) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://finance.sina.com.cn/",
            "Accept": "*/*",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
        content_type = resp.headers.get("Content-Type", "")

    match = re.search(r"charset=([\w-]+)", content_type, flags=re.I)
    encodings = [match.group(1)] if match else []
    encodings.extend(["utf-8", "gb18030"])
    for encoding in encodings:
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def fetch_sina_realtime(symbol: str) -> dict[str, Any]:
    url = f"https://hq.sinajs.cn/list=nf_{urllib.parse.quote(symbol)}"
    text = fetch_text(url, timeout=8)
    match = re.search(r'var\s+hq_str_nf_[A-Za-z0-9]+="([^"]*)"', text)
    if not match:
        raise RuntimeError("新浪实时接口没有返回可解析行情")

    fields = match.group(1).split(",")
    if len(fields) < 17:
        raise RuntimeError(f"新浪实时行情字段不足: {len(fields)}")

    name = fields[0] or symbol
    return {
        "symbol": symbol,
        "name": name,
        "open_interest": to_float(fields[1]),
        "open": to_float(fields[2]),
        "high": to_float(fields[3]),
        "low": to_float(fields[4]),
        "last": to_float(fields[8]) or to_float(fields[7]) or to_float(fields[6]),
        "bid": to_float(fields[9]),
        "ask": to_float(fields[10]),
        "volume": to_float(fields[13]),
        "exchange": fields[14],
        "category": fields[15],
        "date": fields[17] if len(fields) > 17 else "",
        "raw_fields": fields,
        "source": "sina_realtime",
    }


def to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if math.isnan(float(value)):
            return None
        return float(value)
    text = str(value).strip().replace(",", "")
    if not text or text in {"-", "--", "nan", "None", "null"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def json_from_jsonp(text: str) -> Any:
    stripped = text.strip()
    if stripped.startswith("[") or stripped.startswith("{"):
        return json.loads(stripped)

    eq_index = stripped.find("=")
    if eq_index >= 0:
        stripped = stripped[eq_index + 1 :].strip()
    if stripped.endswith(";"):
        stripped = stripped[:-1].strip()

    start = min([i for i in [stripped.find("["), stripped.find("{")] if i >= 0], default=-1)
    if start < 0:
        raise ValueError("No JSON payload found")
    payload = stripped[start:]
    return json.loads(payload)


def normalize_row(row: dict[str, Any], source: str) -> dict[str, Any] | None:
    date = row.get("date") or row.get("trade_date") or row.get("TRADINGDAY") or row.get("_date")
    open_ = to_float(row.get("open") or row.get("OPENPRICE"))
    high = to_float(row.get("high") or row.get("HIGHESTPRICE"))
    low = to_float(row.get("low") or row.get("LOWESTPRICE"))
    close = to_float(row.get("close") or row.get("CLOSEPRICE"))
    volume = to_float(row.get("volume") or row.get("VOLUME"))
    open_interest = to_float(row.get("hold") or row.get("position") or row.get("OPENINTEREST"))

    if not date or close is None:
        return None

    return {
        "date": str(date),
        "open": open_,
        "high": high if high is not None else close,
        "low": low if low is not None else close,
        "close": close,
        "volume": volume,
        "open_interest": open_interest,
        "source": source,
    }


def fetch_sina_daily(symbol: str) -> list[dict[str, Any]]:
    stamp = int(time.time() * 1000)
    encoded_var = urllib.parse.quote(f"_{symbol}{stamp}=")
    urls = [
        "https://stock2.finance.sina.com.cn/futures/api/jsonp.php/"
        f"var%20{encoded_var}/InnerFuturesNewService.getDailyKLine?symbol={urllib.parse.quote(symbol)}",
        "https://stock2.finance.sina.com.cn/futures/api/jsonp.php/"
        f"var%20{encoded_var}/InnerFuturesNewService.getDailyKLine?symbol={urllib.parse.quote(symbol.lower())}",
    ]

    last_error: Exception | None = None
    for url in urls:
        try:
            payload = json_from_jsonp(fetch_text(url))
            if isinstance(payload, list):
                rows = [normalize_row(item, "sina_daily") for item in payload if isinstance(item, dict)]
                rows = [row for row in rows if row]
                if rows:
                    return rows
        except Exception as exc:  # keep trying alternate URL forms
            last_error = exc

    if last_error:
        raise last_error
    raise RuntimeError("Sina returned no usable daily rows")


def date_range_back(days: int) -> list[dt.date]:
    today = dt.date.today()
    return [today - dt.timedelta(days=offset) for offset in range(days)]


def row_matches_symbol(row: dict[str, Any], symbol: str) -> bool:
    wanted = symbol.lower()
    values = {str(value).strip().lower() for value in row.values() if value is not None}
    if wanted in values:
        return True

    product = str(row.get("PRODUCTID") or row.get("productid") or "").strip().lower()
    month = str(row.get("DELIVERYMONTH") or row.get("deliverymonth") or "").strip().lower()
    return bool(product and month and f"{product}{month}" == wanted)


def fetch_shfe_daily(symbol: str, lookback_days: int = 220, min_rows: int = 60) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for day in date_range_back(lookback_days):
        day_text = day.strftime("%Y%m%d")
        url = f"https://www.shfe.com.cn/data/dailydata/kx/kx{day_text}.dat"
        try:
            payload = json.loads(fetch_text(url, timeout=8))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            continue

        instruments = payload.get("o_curinstrument") if isinstance(payload, dict) else None
        if not isinstance(instruments, list):
            continue
        for item in instruments:
            if not isinstance(item, dict) or not row_matches_symbol(item, symbol):
                continue
            item = dict(item)
            item["_date"] = day.isoformat()
            normalized = normalize_row(item, "shfe_daily")
            if normalized:
                rows.append(normalized)
        if len(rows) >= min_rows:
            break

    rows.sort(key=lambda item: item["date"])
    if rows:
        return rows
    raise RuntimeError("SHFE returned no usable rows for this contract")


def moving_average(values: list[float], window: int) -> float:
    return sum(values[-window:]) / window


def ema(values: list[float], span: int) -> float:
    alpha = 2 / (span + 1)
    current = values[0]
    for value in values[1:]:
        current = alpha * value + (1 - alpha) * current
    return current


def pct(value: float) -> str:
    return f"{value:.1f}%"


def analyze(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if len(rows) < 30:
        raise RuntimeError(f"Only {len(rows)} rows fetched; at least 30 are needed")

    closes = [float(row["close"]) for row in rows if row["close"] is not None]
    highs = [float(row["high"]) for row in rows if row["high"] is not None]
    lows = [float(row["low"]) for row in rows if row["low"] is not None]
    if len(closes) < 30 or len(highs) < 20 or len(lows) < 20:
        raise RuntimeError("Fetched rows do not contain enough valid OHLC data")

    price = closes[-1]
    prev = closes[-2]
    ma5 = moving_average(closes, 5)
    ma20 = moving_average(closes, 20)
    ma60 = moving_average(closes, min(60, len(closes)))
    ema12 = ema(closes[-60:], 12)
    ema26 = ema(closes[-60:], 26)
    support = min(lows[-20:])
    resistance = max(highs[-20:])

    signals = [
        ("5日均线在20日均线上方", ma5 > ma20),
        ("12日指数均线在26日指数均线上方", ema12 > ema26),
        ("收盘价高于10日前", price > closes[-10]),
        ("收盘价高于20日均线", price > ma20),
    ]
    long_count = sum(1 for _, ok in signals if ok)
    total = len(signals)
    consistency = max(long_count, total - long_count) / total * 100
    direction = "偏多" if long_count > total / 2 else "偏空" if long_count < total / 2 else "中性"

    return {
        "latest": rows[-1],
        "price": price,
        "change_pct": (price - prev) / prev * 100 if prev else 0.0,
        "ma5": ma5,
        "ma20": ma20,
        "ma60": ma60,
        "ema12": ema12,
        "ema26": ema26,
        "support": support,
        "resistance": resistance,
        "to_support_pct": (price - support) / price * 100 if price else 0.0,
        "to_resistance_pct": (resistance - price) / price * 100 if price else 0.0,
        "signals": signals,
        "long_count": long_count,
        "total": total,
        "consistency": consistency,
        "direction": direction,
        "source": rows[-1]["source"],
        "row_count": len(rows),
    }


def render_report(symbol: str, result: dict[str, Any]) -> str:
    latest = result["latest"]
    lines = [
        f"{symbol} 燃油期货多空一致度检测",
        f"数据日期: {latest['date']}  来源: {result['source']}  样本: {result['row_count']}条",
        f"当前价: {result['price']:.0f}  日涨跌: {pct(result['change_pct'])}",
        "",
        f"方向: {result['direction']}  偏多 {result['long_count']}/{result['total']} 项, "
        f"偏空 {result['total'] - result['long_count']}/{result['total']} 项",
        f"信号一致度: {result['consistency']:.0f}%（指标方向一致性，不是涨跌概率）",
        "",
        "信号明细:",
    ]

    for label, ok in result["signals"]:
        lines.append(f"- {'偏多' if ok else '偏空'}: {label}")

    lines.extend(
        [
            "",
            f"5日均线: {result['ma5']:.0f}  20日均线: {result['ma20']:.0f}  60日均线: {result['ma60']:.0f}",
            f"近20日阻力: {result['resistance']:.0f}（上方 {pct(result['to_resistance_pct'])}）",
            f"近20日支撑: {result['support']:.0f}（下方 {pct(result['to_support_pct'])}）",
            "",
            "手动下单检查:",
            "- 做多前: 先确认止损是否能放在支撑下方，且亏损不超过单笔上限。",
            "- 做空前: 先确认止损是否能放在阻力上方，且不要在急跌后追空。",
            "- 过夜前: 重点看原油外盘、汇率、保证金占用和跳空风险。",
            "",
            "提示: 本报告只做辅助观察，不构成交易建议，不会自动下单。",
        ]
    )
    return "\n".join(lines)


def render_realtime_report(quote: dict[str, Any]) -> str:
    last = quote.get("last")
    open_ = quote.get("open")
    high = quote.get("high")
    low = quote.get("low")
    volume = quote.get("volume")
    open_interest = quote.get("open_interest")
    intraday_pct = (last - open_) / open_ * 100 if last and open_ else None
    range_pct = (high - low) / last * 100 if high and low and last else None

    direction = "日内偏强" if intraday_pct is not None and intraday_pct > 0 else (
        "日内偏弱" if intraday_pct is not None and intraday_pct < 0 else "日内中性"
    )

    lines = [
        f"{quote['symbol']} {quote['name']} 实时行情检测",
        f"数据日期: {quote.get('date') or '未知'}  来源: 新浪实时行情",
        f"最新价: {last:.0f}" if last is not None else "最新价: 无",
        f"开盘: {open_:.0f}  最高: {high:.0f}  最低: {low:.0f}"
        if open_ is not None and high is not None and low is not None
        else "开高低: 数据不足",
        f"成交量: {volume:.0f}  持仓量: {open_interest:.0f}"
        if volume is not None and open_interest is not None
        else "成交/持仓: 数据不足",
        "",
        f"日内状态: {direction}",
    ]
    if intraday_pct is not None:
        lines.append(f"相对开盘: {pct(intraday_pct)}")
    if range_pct is not None:
        lines.append(f"日内振幅: {pct(range_pct)}")

    lines.extend(
        [
            "",
            "手动下单检查:",
            "- 这只是实时快照，不等于买卖信号。",
            "- 追单前先看止损距离、账户可承受亏损、是否临近夜盘或重要数据。",
            "- 做多要确认价格不是刚冲高回落；做空要确认不是急跌后的低位追空。",
            "",
            "提示: 若要加入均线、支撑阻力和多空一致度，可稍后再接稳定日线数据源。",
        ]
    )
    return "\n".join(lines)


def build_deepseek_prompt(quote: dict[str, Any]) -> str:
    last = quote.get("last")
    open_ = quote.get("open")
    high = quote.get("high")
    low = quote.get("low")
    intraday_pct = (last - open_) / open_ * 100 if last and open_ else None
    range_pct = (high - low) / last * 100 if high and low and last else None

    payload = {
        "symbol": quote.get("symbol"),
        "name": quote.get("name"),
        "date": quote.get("date"),
        "last": quote.get("last"),
        "open": quote.get("open"),
        "high": quote.get("high"),
        "low": quote.get("low"),
        "bid": quote.get("bid"),
        "ask": quote.get("ask"),
        "volume": quote.get("volume"),
        "open_interest": quote.get("open_interest"),
        "intraday_pct": round(intraday_pct, 2) if intraday_pct is not None else None,
        "range_pct": round(range_pct, 2) if range_pct is not None else None,
    }

    return (
        "你是中国期货市场的辅助分析和风控助手。"
        "只根据输入行情做手动下单前观察，不允许直接给买入/卖出指令，"
        "不允许使用稳赚、必涨、必跌等确定性表述。\n\n"
        "请用简体中文输出，严格按以下格式。"
        "所有小标题、正文、建议动作和风险描述都必须是中文，不要输出英文句子。\n"
        "1. 市场状态：\n"
        "2. 多头证据：\n"
        "3. 空头风险：\n"
        "4. 追单风险：\n"
        "5. 建议动作：只能从 观察 / 等回踩 / 禁止追多 / 禁止追空 / 小仓试错 中选一个\n"
        "6. 失效条件：\n"
        "7. 手动下单前检查：\n\n"
        "行情数据：\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def call_deepseek(quote: dict[str, Any], model: str, timeout: int = 20) -> str:
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        return (
            "DeepSeek 未启用：没有找到本机环境变量 DEEPSEEK_API_KEY。\n"
            "请先运行 setup_deepseek_key.ps1 设置密钥，然后重新打开 PowerShell 再运行。"
        )

    body = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "你是期货交易辅助分析和风控助手，只做中文观察卡，不提供自动交易指令。",
            },
            {"role": "user", "content": build_deepseek_prompt(quote)},
        ],
        "temperature": 0.2,
        "stream": False,
    }
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        DEEPSEEK_BASE_URL,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"DeepSeek API HTTP {exc.code}: {detail}") from exc

    payload = json.loads(raw)
    try:
        return payload["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"DeepSeek API 返回格式异常: {raw[:500]}") from exc


def fetch_rows(symbol: str) -> list[dict[str, Any]]:
    errors: list[str] = []
    for name, fetcher in [
        ("新浪日线", fetch_sina_daily),
        ("上期所日行情", fetch_shfe_daily),
    ]:
        try:
            rows = fetcher(symbol)
            if rows:
                return rows
        except Exception as exc:
            errors.append(f"{name}: {exc}")
    raise RuntimeError("数据抓取失败。\n" + "\n".join(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description="FU2609 fuel-oil signal checker")
    parser.add_argument("--symbol", default=SYMBOL, help="Contract symbol, default FU2609")
    parser.add_argument(
        "--with-daily",
        action="store_true",
        help="Try slower daily K-line analysis after the realtime quote",
    )
    parser.add_argument(
        "--ai",
        action="store_true",
        help="Ask DeepSeek to create a manual trading observation card",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("DEEPSEEK_MODEL", DEEPSEEK_MODEL),
        help=f"DeepSeek model, default {DEEPSEEK_MODEL}",
    )
    args = parser.parse_args()

    try:
        symbol = args.symbol.upper()
        quote = fetch_sina_realtime(symbol)
        print(render_realtime_report(quote))
        if args.ai:
            print("\n" + "=" * 48)
            print("DeepSeek 手动下单观察卡")
            print("=" * 48)
            print(call_deepseek(quote, args.model))
        if args.with_daily:
            print("\n" + "=" * 48 + "\n")
            rows = fetch_rows(symbol)
            result = analyze(rows)
            print(render_report(symbol, result))
        return 0
    except Exception as exc:
        print(f"运行出错: {exc}")
        print("请检查网络是否可访问新浪实时行情接口，或该合约是否已经挂牌。")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
