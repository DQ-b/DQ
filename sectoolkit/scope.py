# -*- coding: utf-8 -*-
"""
授权范围控制（ScopeGuard）。

这是整个工具包的安全闸门：任何会向目标发送主动流量的操作，都必须先通过
:class:`ScopeGuard.check` 校验。设计原则是 **默认拒绝（default-deny）**——
如果没有显式提供授权范围，所有目标一律拒绝。

授权范围支持四种条目：

* 精确 IP：           ``192.168.1.10``
* CIDR 网段：         ``10.0.0.0/24``
* 精确域名：          ``app.example.com``
* 通配子域：          ``*.example.com``（匹配任意层级子域，但不含裸域本身）

裸域 ``example.com`` 需要单独列出。本地回环（127.0.0.0/8、::1、localhost）
默认**不**放行，必须显式加入授权范围，以避免误把 SSRF/转发目标当成本地。
"""

from __future__ import annotations

import ipaddress
import os
import urllib.parse
from dataclasses import dataclass, field


class ScopeError(PermissionError):
    """目标不在授权范围内时抛出。"""


def _extract_host(target: str) -> str:
    """从 URL / host:port / 裸主机名中提取主机部分。"""
    target = target.strip()
    if not target:
        raise ValueError("空目标")
    # 形如 http://host:port/path
    if "://" in target:
        parsed = urllib.parse.urlsplit(target)
        host = parsed.hostname or ""
    else:
        # 形如 host:port 或 host —— 借助 urlsplit 统一处理 IPv6 字面量
        parsed = urllib.parse.urlsplit("//" + target)
        host = parsed.hostname or target.split(":")[0]
    if not host:
        raise ValueError(f"无法从 {target!r} 解析出主机名")
    return host.lower().rstrip(".")


def _as_ip(host: str) -> ipaddress._BaseAddress | None:
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        return None


@dataclass
class ScopeGuard:
    """授权范围闸门。

    Parameters
    ----------
    networks:
        允许的 IP / CIDR 列表（``ipaddress`` 网络对象）。
    domains:
        允许的精确域名集合。
    wildcards:
        允许的通配子域后缀集合（存储为去掉 ``*.`` 的裸域，如 ``example.com``）。
    acknowledged:
        是否已确认"我已获得对这些目标的测试授权"。未确认时一律拒绝。
    """

    networks: list[ipaddress._BaseNetwork] = field(default_factory=list)
    domains: set[str] = field(default_factory=set)
    wildcards: set[str] = field(default_factory=set)
    acknowledged: bool = False

    # ------------------------------------------------------------------ #
    # 构造
    # ------------------------------------------------------------------ #
    @classmethod
    def from_entries(cls, entries: list[str], *, acknowledged: bool = False) -> "ScopeGuard":
        guard = cls(acknowledged=acknowledged)
        for raw in entries:
            guard.add(raw)
        return guard

    @classmethod
    def from_file(cls, path: str, *, acknowledged: bool = False) -> "ScopeGuard":
        """从范围文件加载。每行一个条目，``#`` 起始为注释，空行忽略。"""
        if not os.path.isfile(path):
            raise FileNotFoundError(f"授权范围文件不存在：{path}")
        entries: list[str] = []
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.split("#", 1)[0].strip()
                if line:
                    entries.append(line)
        if not entries:
            raise ScopeError(f"授权范围文件为空：{path}")
        return cls.from_entries(entries, acknowledged=acknowledged)

    def add(self, entry: str) -> None:
        """向授权范围追加一个条目（IP / CIDR / 域名 / 通配子域）。"""
        entry = entry.strip().lower().rstrip(".")
        if not entry:
            return
        if entry.startswith("*."):
            self.wildcards.add(entry[2:])
            return
        # 尝试当作 IP 网络（含单 IP 与 CIDR）
        try:
            self.networks.append(ipaddress.ip_network(entry, strict=False))
            return
        except ValueError:
            pass
        # 否则视为域名
        self.domains.add(entry)

    # ------------------------------------------------------------------ #
    # 校验
    # ------------------------------------------------------------------ #
    def is_empty(self) -> bool:
        return not (self.networks or self.domains or self.wildcards)

    def allows(self, target: str) -> bool:
        """仅做布尔判断，不抛异常、不检查 acknowledged 标志。"""
        if self.is_empty():
            return False
        host = _extract_host(target)
        ip = _as_ip(host)
        if ip is not None:
            return any(ip in net for net in self.networks)
        # 域名匹配：精确 + 通配后缀
        if host in self.domains:
            return True
        for suffix in self.wildcards:
            if host == suffix or host.endswith("." + suffix):
                return True
        return False

    def check(self, target: str) -> str:
        """校验目标，通过则返回提取出的主机名，否则抛 :class:`ScopeError`。"""
        if not self.acknowledged:
            raise ScopeError(
                "尚未确认测试授权。请通过 --authorize 显式确认你已获得对目标的"
                "书面测试授权后再运行主动扫描。"
            )
        if self.is_empty():
            raise ScopeError(
                "未配置授权范围（默认拒绝）。请用 --scope 或 --scope-file 指定"
                "你被授权测试的目标。"
            )
        host = _extract_host(target)
        if not self.allows(target):
            raise ScopeError(
                f"目标 {host!r} 不在授权范围内，已拒绝。"
                f"如确有授权，请将其加入 --scope / --scope-file。"
            )
        return host

    def describe(self) -> str:
        parts: list[str] = []
        if self.networks:
            parts.append("IP/网段: " + ", ".join(str(n) for n in self.networks))
        if self.domains:
            parts.append("域名: " + ", ".join(sorted(self.domains)))
        if self.wildcards:
            parts.append("通配子域: " + ", ".join("*." + w for w in sorted(self.wildcards)))
        if not parts:
            return "(空——所有目标都会被拒绝)"
        ack = "已确认授权" if self.acknowledged else "⚠ 未确认授权"
        return f"[{ack}] " + " | ".join(parts)
