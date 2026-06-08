# -*- coding: utf-8 -*-
"""
Local FU2609 dashboard.

This wraps the existing realtime checker in a tiny browser UI. It is still a
decision-support tool only and never places orders.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import hmac
import html
import json
import math
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
import urllib.error
from urllib.parse import parse_qs, urlparse
import urllib.request

import fu2609_check


SYMBOL = "FU2609"
DEFAULT_PORT = 8765
MODEL = os.environ.get("DEEPSEEK_MODEL", fu2609_check.DEEPSEEK_MODEL)
APP_DIR = os.path.dirname(os.path.abspath(__file__))

_CACHE: dict[str, tuple[float, Any]] = {}


def to_number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def normalize_symbol(symbol: str) -> str:
    return symbol.strip().upper()


def to_tq_symbol(symbol: str) -> str:
    normalized = normalize_symbol(symbol)
    if normalized.startswith("SHFE."):
        exchange, contract = normalized.split(".", 1)
        return f"{exchange}.{contract.lower()}"
    if normalized.startswith("FU"):
        return f"SHFE.{normalized.lower()}"
    return normalized


def read_tqsdk_auth() -> tuple[str, str] | None:
    user = (
        os.environ.get("TQSDK_USER")
        or os.environ.get("TQ_AUTH_USER")
        or os.environ.get("TQ_USER")
        or ""
    ).strip()
    password = (
        os.environ.get("TQSDK_PASSWORD")
        or os.environ.get("TQ_AUTH_PASSWORD")
        or os.environ.get("TQ_PASSWORD")
        or ""
    ).strip()
    if user and password:
        return user, password

    path = os.path.join(APP_DIR, "tqsdk_auth.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8-sig") as handle:
        payload = json.load(handle)
    user = str(payload.get("user") or payload.get("username") or "").strip()
    password = str(payload.get("password") or "").strip()
    if user and password:
        return user, password
    return None


def tq_datetime_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    if ("-" in text or ":" in text) and text.lower() != "nan":
        return text[:19]
    number = to_number(value)
    if number is None:
        return ""
    try:
        from tqsdk import tafunc

        return tafunc.time_to_datetime(int(number)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""


class TqMarketEngine:
    def __init__(self, symbol: str) -> None:
        self.symbol = normalize_symbol(symbol)
        self.tq_symbol = to_tq_symbol(symbol)
        self._lock = threading.RLock()
        self._quote: dict[str, Any] | None = None
        self._daily: dict[str, Any] | None = None
        self._last_error = "TqSdk 未启动"
        self._running = False
        self._thread: threading.Thread | None = None
        self._api: Any | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        auth = read_tqsdk_auth()
        if not auth:
            self._last_error = "未配置快期账户，使用新浪备用数据"
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, args=(auth,), daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        api = self._api
        if api is not None:
            try:
                api.close()
            except Exception:
                pass

    def get_quote(self) -> dict[str, Any] | None:
        with self._lock:
            return dict(self._quote) if self._quote else None

    def get_daily(self) -> dict[str, Any] | None:
        with self._lock:
            return json.loads(json.dumps(self._daily, ensure_ascii=False)) if self._daily else None

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "running": bool(self._running and self._thread and self._thread.is_alive()),
                "symbol": self.tq_symbol,
                "has_quote": self._quote is not None,
                "has_daily": self._daily is not None,
                "last_error": self._last_error,
            }

    def _run(self, auth_pair: tuple[str, str]) -> None:
        try:
            from tqsdk import TqApi, TqAuth

            user, password = auth_pair
            api = TqApi(auth=TqAuth(user, password), disable_print=True)
            self._api = api
            quote = api.get_quote(self.tq_symbol)
            klines = api.get_kline_serial(self.tq_symbol, 24 * 60 * 60, data_length=80)
            with self._lock:
                self._last_error = ""
            while self._running:
                api.wait_update(deadline=time.time() + 5)
                self._update_quote(quote)
                self._update_daily(klines)
        except Exception as exc:
            with self._lock:
                self._last_error = f"TqSdk 连接失败: {exc}"
        finally:
            try:
                if self._api is not None:
                    self._api.close()
            except Exception:
                pass
            self._api = None
            self._running = False

    def _update_quote(self, quote: Any) -> None:
        last = to_number(getattr(quote, "last_price", None))
        open_ = to_number(getattr(quote, "open", None))
        high = to_number(getattr(quote, "highest", None))
        low = to_number(getattr(quote, "lowest", None))
        bid = to_number(getattr(quote, "bid_price1", None))
        ask = to_number(getattr(quote, "ask_price1", None))
        volume = to_number(getattr(quote, "volume", None))
        open_interest = to_number(getattr(quote, "open_interest", None))
        if last is None:
            return

        intraday_pct = (last - open_) / open_ * 100 if last and open_ else None
        range_pct = (high - low) / last * 100 if high and low and last else None
        status = "日内偏弱" if intraday_pct is not None and intraday_pct < 0 else (
            "日内偏强" if intraday_pct is not None and intraday_pct > 0 else "日内中性"
        )
        quote_time = tq_datetime_text(getattr(quote, "datetime", None))
        payload = {
            "symbol": self.symbol,
            "tq_symbol": self.tq_symbol,
            "name": getattr(quote, "instrument_name", None) or "燃料油2609",
            "date": quote_time[:10] if quote_time else dt.date.today().isoformat(),
            "source": "TqSdk/快期实时行情",
            "last": last,
            "open": open_,
            "high": high,
            "low": low,
            "bid": bid,
            "ask": ask,
            "volume": volume,
            "open_interest": open_interest,
            "intraday_pct": pct(intraday_pct),
            "range_pct": pct(range_pct),
            "status": status,
            "quote_time": quote_time,
            "server_time": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        with self._lock:
            self._quote = payload
            self._last_error = ""

    def _update_daily(self, klines: Any) -> None:
        try:
            import pandas as pd

            df = klines.copy().tail(80)
            df = df.dropna(subset=["close"])
            if len(df) < 30:
                return
            close = pd.to_numeric(df["close"])
            high = pd.to_numeric(df["high"])
            low = pd.to_numeric(df["low"])
            price = float(close.iloc[-1])
            signals = [
                ("5日均线在20日均线上方", bool(close.rolling(5).mean().iloc[-1] > close.rolling(20).mean().iloc[-1])),
                ("12日指数均线在26日指数均线上方", bool(close.ewm(span=12).mean().iloc[-1] > close.ewm(span=26).mean().iloc[-1])),
                ("收盘价高于10日前", bool(close.iloc[-1] > close.iloc[-10])),
                ("收盘价高于20日均线", bool(close.iloc[-1] > close.rolling(20).mean().iloc[-1])),
            ]
            long_count = sum(1 for _, ok in signals if ok)
            total = len(signals)
            resistance = float(high.tail(20).max())
            support = float(low.tail(20).min())
            consistency = max(long_count, total - long_count) / total * 100
            chart = [
                {
                    "date": tq_datetime_text(row["datetime"])[:10],
                    "close": float(row["close"]),
                }
                for _, row in df.tail(60).iterrows()
            ]
            payload = {
                "price": round(price, 2),
                "direction": "偏多" if long_count > total / 2 else "偏空" if long_count < total / 2 else "中性",
                "long_count": long_count,
                "short_count": total - long_count,
                "total": total,
                "consistency": round(consistency),
                "resistance": round(resistance, 2),
                "support": round(support, 2),
                "to_resistance_pct": pct((resistance - price) / price * 100),
                "to_support_pct": pct((price - support) / price * 100),
                "signals": [{"label": label, "long": ok} for label, ok in signals],
                "chart": chart,
                "source": "TqSdk/快期日线",
            }
            with self._lock:
                self._daily = payload
                self._last_error = ""
        except Exception as exc:
            with self._lock:
                self._last_error = f"TqSdk 日线处理失败: {exc}"


TQ_ENGINE = TqMarketEngine(SYMBOL)


def cache_get(key: str, ttl: int) -> Any | None:
    item = _CACHE.get(key)
    if not item:
        return None
    ts, value = item
    if time.time() - ts > ttl:
        return None
    return value


def cache_set(key: str, value: Any) -> Any:
    _CACHE[key] = (time.time(), value)
    return value


def pct(value: float | None) -> float | None:
    return round(value, 2) if value is not None else None


def realtime_payload(symbol: str) -> dict[str, Any]:
    tq_quote = TQ_ENGINE.get_quote()
    if tq_quote:
        return tq_quote

    cached = cache_get(f"quote:{symbol}", 8)
    if cached:
        return cached

    quote = fu2609_check.fetch_sina_realtime(symbol)
    last = quote.get("last")
    open_ = quote.get("open")
    high = quote.get("high")
    low = quote.get("low")
    intraday_pct = (last - open_) / open_ * 100 if last and open_ else None
    range_pct = (high - low) / last * 100 if high and low and last else None
    status = "日内偏弱" if intraday_pct is not None and intraday_pct < 0 else (
        "日内偏强" if intraday_pct is not None and intraday_pct > 0 else "日内中性"
    )

    payload = {
        "symbol": quote.get("symbol"),
        "name": quote.get("name"),
        "date": quote.get("date"),
        "source": "新浪实时行情",
        "fallback_reason": TQ_ENGINE.status().get("last_error"),
        "last": quote.get("last"),
        "open": quote.get("open"),
        "high": quote.get("high"),
        "low": quote.get("low"),
        "bid": quote.get("bid"),
        "ask": quote.get("ask"),
        "volume": quote.get("volume"),
        "open_interest": quote.get("open_interest"),
        "intraday_pct": pct(intraday_pct),
        "range_pct": pct(range_pct),
        "status": status,
        "server_time": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    return cache_set(f"quote:{symbol}", payload)


def daily_payload(symbol: str) -> dict[str, Any]:
    tq_daily = TQ_ENGINE.get_daily()
    if tq_daily:
        return tq_daily

    cached = cache_get(f"daily:{symbol}", 45)
    if cached:
        return cached

    try:
        import akshare as ak
        import pandas as pd
    except ModuleNotFoundError as exc:
        raise RuntimeError("缺少依赖，请先安装 akshare 和 pandas") from exc

    df = ak.futures_zh_daily_sina(symbol=symbol).tail(80)
    if df.empty:
        raise RuntimeError(f"{symbol} 没有可用日线数据")

    close = pd.to_numeric(df["close"])
    high = pd.to_numeric(df["high"])
    low = pd.to_numeric(df["low"])
    price = float(close.iloc[-1])
    signals = [
        ("5日均线在20日均线上方", bool(close.rolling(5).mean().iloc[-1] > close.rolling(20).mean().iloc[-1])),
        ("12日指数均线在26日指数均线上方", bool(close.ewm(span=12).mean().iloc[-1] > close.ewm(span=26).mean().iloc[-1])),
        ("收盘价高于10日前", bool(close.iloc[-1] > close.iloc[-10])),
        ("收盘价高于20日均线", bool(close.iloc[-1] > close.rolling(20).mean().iloc[-1])),
    ]
    long_count = sum(1 for _, ok in signals if ok)
    total = len(signals)
    resistance = float(high.tail(20).max())
    support = float(low.tail(20).min())
    consistency = max(long_count, total - long_count) / total * 100

    date_col = "date" if "date" in df.columns else df.columns[0]
    chart = [
        {"date": str(row[date_col]), "close": float(row["close"])}
        for _, row in df.tail(60).iterrows()
    ]
    payload = {
        "price": round(price, 2),
        "direction": "偏多" if long_count > total / 2 else "偏空" if long_count < total / 2 else "中性",
        "long_count": long_count,
        "short_count": total - long_count,
        "total": total,
        "consistency": round(consistency),
        "resistance": round(resistance, 2),
        "support": round(support, 2),
        "to_resistance_pct": pct((resistance - price) / price * 100),
        "to_support_pct": pct((price - support) / price * 100),
        "signals": [{"label": label, "long": ok} for label, ok in signals],
        "chart": chart,
        "source": "AkShare/新浪日线",
        "fallback_reason": TQ_ENGINE.status().get("last_error"),
    }
    return cache_set(f"daily:{symbol}", payload)


def ai_payload(symbol: str) -> dict[str, Any]:
    quote = realtime_payload(symbol)
    content = fu2609_check.call_deepseek(quote, MODEL)
    return {
        "model": MODEL,
        "content": content,
        "source": quote.get("source"),
        "server_time": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def read_secret(name: str, filename: str) -> str:
    value = os.environ.get(name, "").strip()
    if value:
        return value

    path = os.path.join(APP_DIR, filename)
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if text and not text.startswith("#"):
                return text
    return ""


def feishu_sign(timestamp: str, secret: str) -> str:
    string_to_sign = f"{timestamp}\n{secret}".encode("utf-8")
    digest = hmac.new(string_to_sign, b"", digestmod=hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def build_feishu_message(symbol: str, ai_text: str = "") -> str:
    quote = realtime_payload(symbol)
    daily = daily_payload(symbol)
    lines = [
        "【中文原文】",
        "燃油2609 智能交易辅助系统",
        f"合约: {quote.get('symbol')} {quote.get('name')}",
        f"数据: {quote.get('date') or '未知'} / {quote.get('source')}",
        "",
        f"最新价: {quote.get('last'):.0f}",
        f"日内状态: {quote.get('status')} ({quote.get('intraday_pct')}%)",
        f"最高/最低: {quote.get('high'):.0f} / {quote.get('low'):.0f}",
        f"成交/持仓: {quote.get('volume'):.0f} / {quote.get('open_interest'):.0f}",
        "",
        f"日线方向: {daily.get('direction')} {daily.get('long_count')}/{daily.get('total')}",
        f"信号一致度: {daily.get('consistency')}% (指标方向一致性, 非涨跌概率)",
        f"近20日支撑/阻力: {daily.get('support'):.0f} / {daily.get('resistance'):.0f}",
    ]
    cleaned_ai = ai_text.strip()
    if cleaned_ai and "等待生成" not in cleaned_ai and "失败" not in cleaned_ai:
        lines.extend(["", "智能观察卡:", cleaned_ai])
    lines.extend(
        [
            "",
            "提示: 仅做交易辅助观察, 不自动下单, 不构成投资建议。",
            f"发送时间: {dt.datetime.now():%Y-%m-%d %H:%M:%S}",
        ]
    )
    return "\n".join(lines)


def build_feishu_post_content(symbol: str, ai_text: str = "") -> dict[str, Any]:
    lines = build_feishu_message(symbol, ai_text).splitlines()
    content = [
        [{"tag": "text", "text": anti_translate_text(line if line else " ")}]
        for line in lines
    ]
    return {
        "post": {
            "zh_cn": {
                "title": anti_translate_text("燃油2609提醒：中文原文"),
                "content": content,
            }
        }
    }


def anti_translate_text(text: str) -> str:
    # Feishu may auto-replace bot messages with translated text. Zero-width
    # separators keep the text visually Chinese while making it less likely to
    # be treated as a normal translatable paragraph.
    protected: list[str] = []
    for char in text:
        protected.append(char)
        if "\u3400" <= char <= "\u9fff":
            protected.append("\u200b")
    return "".join(protected)


def chunk_text(text: str, limit: int = 1800) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for line in text.splitlines():
        extra_len = len(line) + 1
        if current and current_len + extra_len > limit:
            chunks.append("\n".join(current))
            current = []
            current_len = 0
        current.append(line)
        current_len += extra_len
    if current:
        chunks.append("\n".join(current))
    return chunks or [text]


def build_feishu_card(symbol: str, ai_text: str = "") -> dict[str, Any]:
    message = build_feishu_message(symbol, ai_text)
    elements: list[dict[str, Any]] = [
        {
            "tag": "note",
            "elements": [
                {
                    "tag": "plain_text",
                    "content": anti_translate_text("中文原文卡片。如果飞书仍显示英文，请在客户端关闭自动翻译或切换为显示原文。"),
                }
            ],
        }
    ]
    for chunk in chunk_text(message):
        elements.append(
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": anti_translate_text(chunk),
                },
            }
        )
    return {
        "config": {
            "wide_screen_mode": True,
            "enable_forward": True,
        },
        "header": {
            "template": "blue",
            "title": {
                "tag": "plain_text",
                "content": anti_translate_text("燃油2609提醒：中文原文"),
            },
        },
        "elements": elements,
    }


def send_feishu_message(symbol: str, ai_text: str = "") -> dict[str, Any]:
    webhook = read_secret("FEISHU_WEBHOOK", "feishu_webhook.txt")
    if not webhook:
        raise RuntimeError(
            "未配置飞书 Webhook。请运行 setup_feishu_webhook.cmd，或在项目目录创建 feishu_webhook.txt。"
        )

    body: dict[str, Any] = {
        "msg_type": "interactive",
        "card": build_feishu_card(symbol, ai_text),
    }
    sign_secret = read_secret("FEISHU_SIGN_SECRET", "feishu_sign_secret.txt")
    if sign_secret:
        timestamp = str(int(time.time()))
        body["timestamp"] = timestamp
        body["sign"] = feishu_sign(timestamp, sign_secret)

    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        webhook,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"飞书返回 HTTP {exc.code}: {detail}") from exc

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        payload = {"raw": raw}

    code = payload.get("code", payload.get("StatusCode", 0))
    if code not in (0, "0"):
        raise RuntimeError(f"飞书发送失败: {raw}")
    return {"message": "已发送到飞书", "response": payload}


def page_html(symbol: str) -> str:
    safe_symbol = html.escape(symbol)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>燃油2609 智能交易辅助系统</title>
  <style>
    :root {{
      --bg: #f6f7f9;
      --panel: #ffffff;
      --ink: #1d2430;
      --muted: #667085;
      --line: #d8dee8;
      --green: #16794c;
      --red: #b42318;
      --yellow: #8a6116;
      --blue: #1f5eff;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Microsoft YaHei", "Segoe UI", Arial, sans-serif;
      background: var(--bg);
      color: var(--ink);
    }}
    button {{
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--ink);
      cursor: pointer;
      font: inherit;
      padding: 8px 12px;
    }}
    button.primary {{ background: var(--blue); color: #fff; border-color: var(--blue); }}
    button:disabled {{ cursor: wait; opacity: .65; }}
    header {{
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 12px;
      align-items: center;
      padding: 16px 22px;
      border-bottom: 1px solid var(--line);
      background: #fff;
      position: sticky;
      top: 0;
      z-index: 5;
    }}
    h1 {{ margin: 0; font-size: 20px; letter-spacing: 0; }}
    .sub {{ margin-top: 4px; color: var(--muted); font-size: 13px; }}
    .actions {{ display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }}
    .toggle {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      min-height: 38px;
      color: var(--muted);
      font-size: 13px;
      white-space: nowrap;
    }}
    .toggle input {{ width: 16px; height: 16px; margin: 0; }}
    main {{
      width: min(1380px, 100%);
      margin: 0 auto;
      padding: 18px 22px 28px;
      display: grid;
      grid-template-columns: minmax(0, 1.55fr) minmax(320px, .9fr);
      gap: 16px;
    }}
    section {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      min-width: 0;
    }}
    .section-head {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 13px 14px;
      border-bottom: 1px solid var(--line);
      gap: 8px;
    }}
    h2 {{ margin: 0; font-size: 15px; letter-spacing: 0; }}
    .status {{
      border-radius: 999px;
      padding: 4px 8px;
      font-size: 12px;
      border: 1px solid var(--line);
      color: var(--muted);
      white-space: nowrap;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 1px;
      background: var(--line);
      border-bottom: 1px solid var(--line);
    }}
    .metric {{ background: #fff; padding: 14px; min-height: 84px; }}
    .label {{ color: var(--muted); font-size: 12px; margin-bottom: 7px; }}
    .value {{ font-size: 25px; font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
    .up {{ color: var(--green); }}
    .down {{ color: var(--red); }}
    .chart-wrap {{ padding: 14px; min-height: 360px; }}
    canvas {{ display: block; width: 100%; height: 320px; }}
    .split {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 1px;
      background: var(--line);
      border-top: 1px solid var(--line);
    }}
    .box {{ background: #fff; padding: 14px; min-height: 112px; }}
    .signal-row {{
      display: flex;
      justify-content: space-between;
      gap: 10px;
      padding: 9px 0;
      border-bottom: 1px solid #edf0f5;
      font-size: 14px;
    }}
    .signal-row:last-child {{ border-bottom: 0; }}
    .ai {{ padding: 14px; }}
    .ai-text {{
      white-space: pre-wrap;
      line-height: 1.55;
      margin: 0;
      color: #263241;
      font-size: 14px;
    }}
    .risk-note {{
      margin-top: 12px;
      padding: 11px 12px;
      border: 1px solid #ead7a8;
      border-radius: 6px;
      background: #fff8e6;
      color: var(--yellow);
      font-size: 13px;
      line-height: 1.45;
    }}
    .notice {{
      display: none;
      margin-bottom: 12px;
      padding: 10px 12px;
      border: 1px solid var(--line);
      border-radius: 6px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.45;
    }}
    .notice.show {{ display: block; }}
    .notice.ok {{ border-color: #9ed7b5; background: #eefaf3; color: var(--green); }}
    .notice.err {{ border-color: #e8a29b; background: #fff1f0; color: var(--red); }}
    .span-2 {{ grid-column: span 2; }}
    @media (max-width: 980px) {{
      header {{ grid-template-columns: 1fr; }}
      .actions {{ justify-content: flex-start; }}
      main {{ grid-template-columns: 1fr; padding: 14px; }}
      .grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .span-2 {{ grid-column: span 1; }}
    }}
    @media (max-width: 560px) {{
      .grid, .split {{ grid-template-columns: 1fr; }}
      .value {{ font-size: 22px; }}
    }}
  </style>
</head>
<body>
  <header>
    <div>
      <h1>燃油2609 智能交易辅助系统</h1>
      <div class="sub"><span id="symbol">{safe_symbol}</span> · <span id="source">等待行情</span> · <span id="clock">--</span></div>
    </div>
    <div class="actions">
      <button id="refreshBtn">刷新行情</button>
      <button id="aiBtn" class="primary">AI 分析</button>
      <button id="feishuBtn">发送飞书</button>
      <label class="toggle"><input id="autoFeishu" type="checkbox" checked />AI 后自动发</label>
    </div>
  </header>
  <main>
    <section>
      <div class="section-head">
        <h2>实时行情</h2>
        <span id="state" class="status">连接中</span>
      </div>
      <div class="grid">
        <div class="metric"><div class="label">最新价</div><div id="last" class="value">--</div></div>
        <div class="metric"><div class="label">相对开盘</div><div id="intraday" class="value">--</div></div>
        <div class="metric"><div class="label">最高 / 最低</div><div id="range" class="value">--</div></div>
        <div class="metric"><div class="label">成交 / 持仓</div><div id="volume" class="value">--</div></div>
      </div>
      <div class="chart-wrap">
        <canvas id="chart" width="900" height="320"></canvas>
      </div>
      <div class="split">
        <div class="box">
          <div class="label">日线方向</div>
          <div id="dailyDirection" class="value">--</div>
        </div>
        <div class="box">
          <div class="label">近20日支撑 / 阻力</div>
          <div id="levels" class="value">--</div>
        </div>
      </div>
    </section>
    <section>
      <div class="section-head">
        <h2>信号与 AI 观察</h2>
        <span id="aiState" class="status">未分析</span>
      </div>
      <div class="ai">
        <div id="notice" class="notice"></div>
        <div id="signals"></div>
        <pre id="aiText" class="ai-text">AI 观察卡等待生成。</pre>
        <div class="risk-note">本页只做交易辅助观察，不自动下单，不构成投资建议；期货交易存在高杠杆与本金损失风险。</div>
      </div>
    </section>
  </main>
  <script>
    const symbol = "{safe_symbol}";
    const fmt = (n, digits = 0) => Number.isFinite(Number(n)) ? Number(n).toLocaleString("zh-CN", {{ maximumFractionDigits: digits }}) : "--";
    const signed = (n) => Number.isFinite(Number(n)) ? `${{Number(n) > 0 ? "+" : ""}}${{Number(n).toFixed(2)}}%` : "--";

    function setBusy(button, busy) {{
      button.disabled = busy;
    }}

    function showNotice(message, kind = "") {{
      notice.textContent = message;
      notice.className = `notice show ${{kind}}`;
    }}

    function drawChart(points) {{
      const canvas = document.getElementById("chart");
      const ctx = canvas.getContext("2d");
      const w = canvas.width;
      const h = canvas.height;
      ctx.clearRect(0, 0, w, h);
      ctx.fillStyle = "#ffffff";
      ctx.fillRect(0, 0, w, h);
      if (!points || points.length < 2) {{
        ctx.fillStyle = "#667085";
        ctx.fillText("暂无日线数据", 20, 34);
        return;
      }}
      const values = points.map(p => Number(p.close));
      const min = Math.min(...values);
      const max = Math.max(...values);
      const pad = 26;
      const x = i => pad + i * ((w - pad * 2) / (points.length - 1));
      const y = v => h - pad - ((v - min) / Math.max(1, max - min)) * (h - pad * 2);
      ctx.strokeStyle = "#d8dee8";
      ctx.lineWidth = 1;
      for (let i = 0; i < 4; i++) {{
        const yy = pad + i * ((h - pad * 2) / 3);
        ctx.beginPath();
        ctx.moveTo(pad, yy);
        ctx.lineTo(w - pad, yy);
        ctx.stroke();
      }}
      ctx.strokeStyle = values.at(-1) >= values[0] ? "#16794c" : "#b42318";
      ctx.lineWidth = 3;
      ctx.beginPath();
      values.forEach((v, i) => i ? ctx.lineTo(x(i), y(v)) : ctx.moveTo(x(i), y(v)));
      ctx.stroke();
      ctx.fillStyle = "#1d2430";
      ctx.font = "13px Microsoft YaHei, Segoe UI, sans-serif";
      ctx.fillText(`近60日收盘 ${{fmt(min)}} - ${{fmt(max)}}`, pad, 18);
    }}

    async function loadMarket() {{
      setBusy(refreshBtn, true);
      state.textContent = "更新中";
      try {{
        const [quoteRes, dailyRes] = await Promise.all([
          fetch(`/api/quote?symbol=${{encodeURIComponent(symbol)}}`),
          fetch(`/api/daily?symbol=${{encodeURIComponent(symbol)}}`)
        ]);
        const quote = await quoteRes.json();
        const daily = await dailyRes.json();
        if (!quote.ok) throw new Error(quote.error);
        if (!daily.ok) throw new Error(daily.error);
        source.textContent = `${{quote.data.source}} · ${{quote.data.date || "未知日期"}}`;
        clock.textContent = quote.data.server_time;
        state.textContent = quote.data.status;
        state.className = `status ${{quote.data.intraday_pct < 0 ? "down" : quote.data.intraday_pct > 0 ? "up" : ""}}`;
        last.textContent = fmt(quote.data.last);
        intraday.textContent = signed(quote.data.intraday_pct);
        intraday.className = `value ${{quote.data.intraday_pct < 0 ? "down" : quote.data.intraday_pct > 0 ? "up" : ""}}`;
        range.textContent = `${{fmt(quote.data.high)}} / ${{fmt(quote.data.low)}}`;
        volume.textContent = `${{fmt(quote.data.volume)}} / ${{fmt(quote.data.open_interest)}}`;
        dailyDirection.textContent = `${{daily.data.direction}} ${{daily.data.long_count}}/${{daily.data.total}} · 一致度 ${{daily.data.consistency}}%`;
        dailyDirection.className = `value ${{daily.data.direction === "偏多" ? "up" : daily.data.direction === "偏空" ? "down" : ""}}`;
        levels.textContent = `${{fmt(daily.data.support)}} / ${{fmt(daily.data.resistance)}}`;
        signals.innerHTML = daily.data.signals.map(s => `
          <div class="signal-row">
            <span>${{s.label}}</span>
            <strong class="${{s.long ? "up" : "down"}}">${{s.long ? "偏多" : "偏空"}}</strong>
          </div>`).join("");
        drawChart(daily.data.chart);
      }} catch (err) {{
        state.textContent = "更新失败";
        aiText.textContent = `行情更新失败：${{err.message}}`;
      }} finally {{
        setBusy(refreshBtn, false);
      }}
    }}

    async function runAi() {{
      setBusy(aiBtn, true);
      aiState.textContent = "分析中";
      try {{
        const res = await fetch(`/api/ai?symbol=${{encodeURIComponent(symbol)}}`);
        const payload = await res.json();
        if (!payload.ok) throw new Error(payload.error);
        aiState.textContent = payload.data.model;
        aiText.textContent = payload.data.content;
        if (autoFeishu.checked) {{
          showNotice("AI 分析完成，正在自动发送飞书...", "");
          try {{
            await postFeishu(payload.data.content);
            showNotice("AI 分析完成，已自动发送到飞书。", "ok");
          }} catch (sendErr) {{
            showNotice(`AI 分析完成，但飞书发送失败：${{sendErr.message}}`, "err");
          }}
        }} else {{
          showNotice("AI 分析完成。", "ok");
        }}
      }} catch (err) {{
        aiState.textContent = "AI 异常";
        aiText.textContent = `AI 分析失败：${{err.message}}`;
      }} finally {{
        setBusy(aiBtn, false);
      }}
    }}

    async function postFeishu(aiTextOverride = "") {{
      const aiTextNow = aiTextOverride || aiText.textContent.trim();
      const includeAi = aiTextNow && !aiTextNow.includes("等待生成") && !aiTextNow.includes("失败");
      const res = await fetch(`/api/feishu?symbol=${{encodeURIComponent(symbol)}}`, {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{ ai_text: includeAi ? aiTextNow : "" }})
      }});
      const payload = await res.json();
      if (!payload.ok) throw new Error(payload.error);
      return payload;
    }}

    async function sendFeishu() {{
      setBusy(feishuBtn, true);
      showNotice("正在发送到飞书...", "");
      try {{
        await postFeishu();
        showNotice("已发送到飞书。", "ok");
      }} catch (err) {{
        showNotice(`飞书发送失败：${{err.message}}`, "err");
      }} finally {{
        setBusy(feishuBtn, false);
      }}
    }}

    refreshBtn.addEventListener("click", loadMarket);
    aiBtn.addEventListener("click", runAi);
    feishuBtn.addEventListener("click", sendFeishu);
    loadMarket();
    setInterval(loadMarket, 30000);
  </script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[{dt.datetime.now():%H:%M:%S}] {fmt % args}")

    def send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_html(self, content: str) -> None:
        data = content.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        if length > 200_000:
            raise RuntimeError("请求内容过大")
        raw = self.rfile.read(length).decode("utf-8", errors="replace")
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise RuntimeError("请求格式不正确")
        return payload

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        symbol = query.get("symbol", [SYMBOL])[0].upper()
        try:
            if parsed.path == "/":
                self.send_html(page_html(symbol))
            elif parsed.path == "/api/quote":
                self.send_json({"ok": True, "data": realtime_payload(symbol)})
            elif parsed.path == "/api/daily":
                self.send_json({"ok": True, "data": daily_payload(symbol)})
            elif parsed.path == "/api/ai":
                self.send_json({"ok": True, "data": ai_payload(symbol)})
            elif parsed.path == "/api/source":
                self.send_json({"ok": True, "data": TQ_ENGINE.status()})
            else:
                self.send_json({"ok": False, "error": "Not found"}, status=404)
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=500)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        symbol = query.get("symbol", [SYMBOL])[0].upper()
        try:
            if parsed.path == "/api/feishu":
                payload = self.read_json_body()
                ai_text = str(payload.get("ai_text", "") or "")
                self.send_json({"ok": True, "data": send_feishu_message(symbol, ai_text)})
            else:
                self.send_json({"ok": False, "error": "Not found"}, status=404)
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=500)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local FU2609 dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--disable-tqsdk", action="store_true", help="Disable TqSdk/Kuaqi market engine")
    args = parser.parse_args()

    if not args.disable_tqsdk:
        TQ_ENGINE.start()

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"FU2609 dashboard: http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopping FU2609 dashboard")
    finally:
        TQ_ENGINE.stop()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
