# -*- coding: utf-8 -*-
"""
原始 HTTP 请求解析。

支持把 Burp/ZAP 里"复制为原始请求"保存的文本直接拿来 fuzz，例如::

    POST /login?next=/ HTTP/1.1
    Host: app.example.com
    Content-Type: application/x-www-form-urlencoded
    Cookie: session=abc

    user=admin&pass=FUZZ

``FUZZ`` 标记可出现在请求行、任意头部或请求体中。解析时会：

* 由请求行的 method/target 与 ``Host`` 头推导完整 URL；
* 丢弃 ``Content-Length``（交给 HTTP 客户端按实际 body 重算）与
  ``Accept-Encoding``（避免响应被压缩、影响差异分析）。
"""

from __future__ import annotations

from dataclasses import dataclass, field

# 发送时主动剔除的头部（小写）
_DROP_HEADERS = {"content-length", "accept-encoding"}


@dataclass
class RawRequest:
    method: str
    url: str
    headers: dict[str, str] = field(default_factory=dict)
    body: str | None = None


def parse_raw_request(text: str, *, scheme: str = "http") -> RawRequest:
    """把原始 HTTP 请求文本解析为 :class:`RawRequest`。"""
    # 统一换行，并按首个空行切分 头部 / 正文
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if "\n\n" in normalized:
        head, body = normalized.split("\n\n", 1)
    else:
        head, body = normalized, ""

    lines = [ln for ln in head.split("\n")]
    if not lines or not lines[0].strip():
        raise ValueError("空的请求行，无法解析原始请求")

    request_line = lines[0].strip()
    parts = request_line.split()
    if len(parts) < 2:
        raise ValueError(f"无法解析请求行：{request_line!r}")
    method, target = parts[0].upper(), parts[1]

    headers: dict[str, str] = {}
    host = ""
    for ln in lines[1:]:
        if not ln.strip() or ":" not in ln:
            continue
        key, _, value = ln.partition(":")
        key, value = key.strip(), value.strip()
        if key.lower() == "host":
            host = value
        if key.lower() in _DROP_HEADERS:
            continue
        headers[key] = value

    # 推导完整 URL
    if target.startswith(("http://", "https://")):
        url = target
    else:
        if not host:
            raise ValueError("原始请求缺少 Host 头，且 target 不是绝对 URL，无法推导 URL")
        url = f"{scheme}://{host}{target if target.startswith('/') else '/' + target}"

    body_clean = body if body.strip() else None
    return RawRequest(method=method, url=url, headers=headers, body=body_clean)
