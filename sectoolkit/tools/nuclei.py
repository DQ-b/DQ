# -*- coding: utf-8 -*-
"""
nuclei 封装：调用 ProjectDiscovery 的 nuclei 做基于模板的漏洞扫描，
并解析其 JSONL 输出为统一的 :class:`Finding`。

用 ``-jsonl`` 让 nuclei 每行输出一个 JSON 结果，再逐行解析（容忍坏行），
无需额外依赖。所有目标在执行前经 ScopeGuard 校验。
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from ..reporting import Finding, Severity
from ..scope import ScopeGuard
from .base import ExternalTool, ToolResult

# nuclei 的 severity 字符串 → 本工具包的级别
_SEV_MAP = {
    "info": Severity.INFO, "low": Severity.LOW, "medium": Severity.MEDIUM,
    "high": Severity.HIGH, "critical": Severity.CRITICAL, "unknown": Severity.INFO,
}


@dataclass
class NucleiScanner:
    scope: ScopeGuard
    binary: str = "nuclei"

    def __post_init__(self) -> None:
        self.tool = ExternalTool(self.binary)

    def available(self) -> bool:
        return self.tool.available()

    # ------------------------------------------------------------------ #
    def build_args(
        self,
        target: str,
        *,
        severity: str | None = None,    # 如 "medium,high,critical"
        templates: str | None = None,   # -t 的值，模板路径/标签
        rate_limit: int | None = None,
        extra: list[str] | None = None,
    ) -> list[str]:
        # -jsonl 行式 JSON；-silent 抑制横幅；-duc 跳过模板自动更新（离线/受限网络更稳）
        args: list[str] = ["-u", target, "-jsonl", "-silent", "-duc"]
        if severity:
            args += ["-severity", severity]
        if templates:
            args += ["-t", templates]
        if rate_limit:
            args += ["-rate-limit", str(rate_limit)]
        if extra:
            args += extra
        return args

    # ------------------------------------------------------------------ #
    def scan(self, target: str, *, timeout: float = 1200.0, **kw) -> tuple[ToolResult, list[Finding]]:
        self.scope.check(target)
        args = self.build_args(target, **kw)
        result = self.tool.run(args, timeout=timeout)
        findings = self.parse_jsonl(result.stdout)
        if not result.ok and not findings and result.stderr.strip():
            findings.append(Finding(
                title="nuclei 执行提示", target=target, severity=Severity.INFO,
                source="nuclei", detail=result.stderr.strip()[:500],
            ))
        return result, findings

    # ------------------------------------------------------------------ #
    @staticmethod
    def parse_jsonl(text: str) -> list[Finding]:
        findings: list[Finding] = []
        for line in text.splitlines():
            line = line.strip()
            if not line or not line.startswith("{"):
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            info = obj.get("info", {}) or {}
            sev = _SEV_MAP.get(str(info.get("severity", "info")).lower(), Severity.INFO)
            name = info.get("name") or obj.get("template-id", "nuclei finding")
            matched = obj.get("matched-at") or obj.get("host", "")
            findings.append(Finding(
                title=f"[nuclei] {name}",
                target=matched or obj.get("host", "?"),
                severity=sev,
                source="nuclei",
                detail=info.get("description", "") or f"模板: {obj.get('template-id', '')}",
                evidence={
                    "template_id": obj.get("template-id", ""),
                    "type": obj.get("type", ""),
                    "matched_at": matched,
                    "matcher_name": obj.get("matcher-name", ""),
                    "extracted": obj.get("extracted-results", []),
                },
                tags=list(info.get("tags", []) or []),
            ))
        return findings
