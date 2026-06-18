# -*- coding: utf-8 -*-
"""
HTTP 模糊测试引擎。

核心思路：

1. 用 ``FUZZ`` 标记指定注入点（URL 路径 / 查询参数 / 请求头 / 请求体均可），
   引擎把每个载荷替换进标记位置后并发发送。
2. 先发一个良性"基线"请求，记录正常响应的状态码/长度/词数。
3. 对每个载荷响应做差异分析 + 特征匹配，识别值得关注的异常：
   * SQL 报错特征  → 疑似 SQL 注入
   * 载荷被原样反射 → 疑似 XSS
   * 状态码/长度显著偏离基线、出现 5xx、明显超时 → 异常行为

引擎只负责**发现征兆并报告**，不做利用。所有目标都先经 ScopeGuard 校验。
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

from ..http_client import HttpClient, HttpResponse
from ..reporting import Finding, Severity
from ..scope import ScopeGuard
from . import payloads as pl

FUZZ_MARKER = "FUZZ"


@dataclass
class FuzzResult:
    payload: str
    request_url: str
    where: str                      # 注入位置描述
    response: HttpResponse
    anomalies: list[str] = field(default_factory=list)

    @property
    def interesting(self) -> bool:
        return bool(self.anomalies)


@dataclass
class HttpFuzzer:
    scope: ScopeGuard
    client: HttpClient = field(default_factory=HttpClient)
    threads: int = 10
    delay: float = 0.0              # 每个请求后的限速间隔（秒）
    length_tolerance: float = 0.30  # 长度相对基线的偏离阈值（30%）

    # ------------------------------------------------------------------ #
    # 基线
    # ------------------------------------------------------------------ #
    def _baseline(self, method: str, url: str, **kw) -> HttpResponse | None:
        try:
            return self.client.request(method, url, **kw)
        except Exception:  # noqa: BLE001
            return None

    # ------------------------------------------------------------------ #
    # 分析
    # ------------------------------------------------------------------ #
    def _analyse(
        self, payload: str, resp: HttpResponse, baseline: HttpResponse | None
    ) -> list[str]:
        anomalies: list[str] = []
        if resp.error:
            anomalies.append(f"请求异常/超时: {resp.error}")
            return anomalies

        sig = pl.has_sql_error(resp.text)
        if sig:
            anomalies.append(f"响应含 SQL 报错特征: {sig!r}（疑似 SQLi）")

        # 反射检测：原样且未转义地出现 → 可能 XSS
        raw = payload.strip()
        if raw and len(raw) >= 4 and raw in resp.text:
            if any(c in raw for c in "<>\"'") and "stk" in raw.lower() or "<" in raw:
                anomalies.append("载荷被原样反射到响应中（疑似 XSS / 注入点）")

        if resp.status >= 500:
            anomalies.append(f"服务端错误 {resp.status}（载荷可能破坏了后端处理）")

        if baseline is not None and baseline.status:
            if resp.status != baseline.status and resp.status not in (0,):
                anomalies.append(f"状态码偏离基线: {baseline.status} → {resp.status}")
            base_len = max(baseline.length, 1)
            delta = abs(resp.length - baseline.length) / base_len
            if delta > self.length_tolerance:
                anomalies.append(
                    f"响应长度偏离基线 {delta:.0%}（{baseline.length}→{resp.length}）"
                )
        return anomalies

    # ------------------------------------------------------------------ #
    # 通用 FUZZ-marker 模糊测试
    # ------------------------------------------------------------------ #
    def fuzz(
        self,
        template_url: str,
        payload_list: list[str],
        *,
        method: str = "GET",
        headers: dict | None = None,
        data: str | None = None,
        where: str = "url",
    ) -> list[FuzzResult]:
        """对含 ``FUZZ`` 标记的请求做模糊测试。

        ``FUZZ`` 可出现在 ``template_url``、某个 header 值或 ``data`` 中。
        """
        self.scope.check(template_url)

        # 基线：用空字符串替换标记
        base_url = template_url.replace(FUZZ_MARKER, "")
        base_headers = {k: v.replace(FUZZ_MARKER, "") for k, v in (headers or {}).items()}
        base_data = data.replace(FUZZ_MARKER, "") if data else None
        baseline = self._baseline(method, base_url, headers=base_headers, data=base_data)

        def one(payload: str) -> FuzzResult:
            url = template_url.replace(FUZZ_MARKER, payload)
            hdrs = {k: v.replace(FUZZ_MARKER, payload) for k, v in (headers or {}).items()}
            body = data.replace(FUZZ_MARKER, payload) if data else None
            resp = self.client.request(method, url, headers=hdrs, data=body)
            if self.delay:
                time.sleep(self.delay)
            return FuzzResult(payload, url, where, resp, self._analyse(payload, resp, baseline))

        return self._run(one, payload_list)

    # ------------------------------------------------------------------ #
    # 单参数模糊测试
    # ------------------------------------------------------------------ #
    def fuzz_param(
        self, url: str, param: str, payload_list: list[str], *, method: str = "GET"
    ) -> list[FuzzResult]:
        """对某个查询参数注入载荷。其余参数保持原值。"""
        import urllib.parse

        self.scope.check(url)
        parts = urllib.parse.urlsplit(url)
        query = dict(urllib.parse.parse_qsl(parts.query, keep_blank_values=True))
        baseline_q = dict(query)
        baseline_q[param] = baseline_q.get(param, "")
        base_url = parts._replace(query=urllib.parse.urlencode(baseline_q)).geturl()
        baseline = self._baseline(method, base_url)

        def one(payload: str) -> FuzzResult:
            q = dict(query)
            q[param] = payload
            target = parts._replace(query=urllib.parse.urlencode(q)).geturl()
            resp = self.client.request(method, target)
            if self.delay:
                time.sleep(self.delay)
            return FuzzResult(
                payload, target, f"参数 {param}", resp, self._analyse(payload, resp, baseline)
            )

        return self._run(one, payload_list)

    # ------------------------------------------------------------------ #
    # 原始请求模糊测试（Burp 风格请求文件）
    # ------------------------------------------------------------------ #
    def fuzz_request(
        self, raw_text: str, payload_list: list[str], *, scheme: str = "http"
    ) -> list[FuzzResult]:
        """对一份含 ``FUZZ`` 标记的原始 HTTP 请求做模糊测试。"""
        from .request import parse_raw_request

        base_req = parse_raw_request(raw_text.replace(FUZZ_MARKER, ""), scheme=scheme)
        self.scope.check(base_req.url)
        baseline = self._baseline(
            base_req.method, base_req.url, headers=base_req.headers, data=base_req.body
        )

        def one(payload: str) -> FuzzResult:
            req = parse_raw_request(raw_text.replace(FUZZ_MARKER, payload), scheme=scheme)
            resp = self.client.request(req.method, req.url, headers=req.headers, data=req.body)
            if self.delay:
                time.sleep(self.delay)
            return FuzzResult(
                payload, req.url, "raw-request", resp, self._analyse(payload, resp, baseline)
            )

        return self._run(one, payload_list)

    # ------------------------------------------------------------------ #
    # 目录/路径爆破
    # ------------------------------------------------------------------ #
    def dirbust(
        self, base_url: str, words: list[str], *, method: str = "GET"
    ) -> list[FuzzResult]:
        """把词表逐个拼到路径后探测存在的资源。"""
        self.scope.check(base_url)
        root = base_url.rstrip("/") + "/"
        # 用一个大概率不存在的随机路径建立"404 基线"，识别软 404
        baseline = self._baseline(method, root + "sectoolkit_nonexistent_a9b8c7")

        def one(word: str) -> FuzzResult:
            target = root + word.lstrip("/")
            resp = self.client.request(method, target)
            if self.delay:
                time.sleep(self.delay)
            anomalies: list[str] = []
            if resp.error or resp.status == 0:
                # 连接失败/不服务 HTTP：目录探测里这不是"发现"，直接略过避免刷屏
                return FuzzResult(word, target, "path", resp, [])
            if resp.status != 404:
                # 与软 404 基线长度差异明显，才认为是"命中"
                if baseline and baseline.status == resp.status:
                    base_len = max(baseline.length, 1)
                    if abs(resp.length - baseline.length) / base_len <= 0.05:
                        return FuzzResult(word, target, "path", resp, [])
                anomalies.append(f"资源可能存在: HTTP {resp.status} (len={resp.length})")
            return FuzzResult(word, target, "path", resp, anomalies)

        return self._run(one, words)

    # ------------------------------------------------------------------ #
    def _run(self, fn, items: list[str]) -> list[FuzzResult]:
        results: list[FuzzResult] = []
        workers = max(1, self.threads)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(fn, it) for it in items]
            for fut in as_completed(futures):
                results.append(fut.result())
        return results

    # ------------------------------------------------------------------ #
    @staticmethod
    def to_findings(results: list[FuzzResult], source: str = "fuzzer") -> list[Finding]:
        findings: list[Finding] = []
        for r in results:
            if not r.interesting:
                continue
            sev = Severity.LOW
            joined = " ".join(r.anomalies).lower()
            if "sqli" in joined or "sql 报错" in joined:
                sev = Severity.HIGH
            elif "xss" in joined or "服务端错误" in joined:
                sev = Severity.MEDIUM
            findings.append(
                Finding(
                    title=f"Fuzz 异常 @ {r.where}",
                    target=r.request_url,
                    severity=sev,
                    source=source,
                    detail="; ".join(r.anomalies),
                    evidence={
                        "payload": r.payload,
                        "status": r.response.status,
                        "length": r.response.length,
                        "elapsed": round(r.response.elapsed, 3),
                    },
                    tags=["fuzz"],
                )
            )
        return findings
