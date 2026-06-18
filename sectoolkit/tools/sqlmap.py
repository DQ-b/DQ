# -*- coding: utf-8 -*-
"""
sqlmap 封装：以非交互（``--batch``）方式驱动 sqlmap 检测 SQL 注入，
并从输出中提取"是否可注入 / 注入点 / 后端 DBMS"等关键信息。

sqlmap 自身行为复杂，这里只做**检测级别**的安全封装（默认低风险等级），
不开启数据导出 / OS shell 等高危选项；如需要可通过 ``extra`` 自行追加，
但请确保在授权范围内谨慎使用。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..reporting import Finding, Severity
from ..scope import ScopeGuard
from .base import ExternalTool, ToolResult


@dataclass
class SqlmapScanner:
    scope: ScopeGuard
    binary: str = "sqlmap"

    def __post_init__(self) -> None:
        self.tool = ExternalTool(self.binary)

    def available(self) -> bool:
        return self.tool.available()

    # ------------------------------------------------------------------ #
    def build_args(
        self,
        url: str,
        *,
        data: str | None = None,
        level: int = 1,
        risk: int = 1,
        technique: str | None = None,
        extra: list[str] | None = None,
    ) -> list[str]:
        args = ["-u", url, "--batch", f"--level={level}", f"--risk={risk}", "--disable-coloring"]
        if data:
            args += ["--data", data]
        if technique:
            args += ["--technique", technique]
        if extra:
            args += extra
        return args

    # ------------------------------------------------------------------ #
    def scan(self, url: str, *, timeout: float = 900.0, **kw) -> tuple[ToolResult, list[Finding]]:
        self.scope.check(url)
        args = self.build_args(url, **kw)
        result = self.tool.run(args, timeout=timeout)
        findings = self.parse_output(result.stdout + "\n" + result.stderr, url)
        return result, findings

    # ------------------------------------------------------------------ #
    @staticmethod
    def parse_output(text: str, url: str) -> list[Finding]:
        findings: list[Finding] = []
        low = text.lower()

        # 真实 sqlmap 有两种常见呈现：
        #   1) 注入点汇总块里的 "Parameter: id (GET)"
        #   2) 日志行里的 "GET parameter 'id' is vulnerable" / "... injectable"
        params_found: set[str] = set()
        params_found.update(re.findall(r"^\s*Parameter:\s*([^\s(]+)", text, flags=re.M))
        params_found.update(re.findall(r"parameter '([^']+)'\s+(?:is|appears)", text, flags=re.I))
        injectable_params = sorted(params_found)

        dbms_match = re.search(r"back-end DBMS:\s*(.+)", text, flags=re.I)
        dbms = dbms_match.group(1).strip() if dbms_match else ""

        vulnerable = (
            bool(injectable_params)
            or "is vulnerable" in low
            or "sqlmap identified the following injection" in low
        )
        if vulnerable:
            params = ", ".join(injectable_params) or "（见原始输出）"
            findings.append(
                Finding(
                    title="发现 SQL 注入点",
                    target=url, severity=Severity.CRITICAL, source="sqlmap",
                    detail=f"可注入参数: {params}" + (f" | 后端 DBMS: {dbms}" if dbms else ""),
                    evidence={"injectable_params": injectable_params, "dbms": dbms},
                    tags=["sqli"],
                )
            )
        elif "all tested parameters do not appear to be injectable" in low:
            findings.append(
                Finding(
                    title="未发现 SQL 注入",
                    target=url, severity=Severity.INFO, source="sqlmap",
                    detail="sqlmap 在当前 level/risk 下未发现可注入参数。",
                    tags=["sqli"],
                )
            )
        return findings
