# -*- coding: utf-8 -*-
"""
gobuster 封装：调用 gobuster 的 ``dir`` 模式做目录/文件爆破，解析命中行为
统一的 :class:`Finding`。

gobuster 必须指定词表文件。若调用方未提供，则把内置的 ``COMMON_PATHS``
临时落盘当词表，做到开箱即用。所有目标在执行前经 ScopeGuard 校验。
"""

from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass

from ..fuzzer import payloads as pl
from ..reporting import Finding, Severity
from ..scope import ScopeGuard
from .base import ExternalTool, ToolResult

# 形如:  /admin                (Status: 301) [Size: 312] [--> /admin/]
_LINE_RE = re.compile(r"^(\S+)\s+\(Status:\s*(\d+)\)\s*\[Size:\s*(\d+)\]")


@dataclass
class GobusterScanner:
    scope: ScopeGuard
    binary: str = "gobuster"

    def __post_init__(self) -> None:
        self.tool = ExternalTool(self.binary)

    def available(self) -> bool:
        return self.tool.available()

    # ------------------------------------------------------------------ #
    def build_args(
        self,
        url: str,
        wordlist: str,
        *,
        extensions: str | None = None,
        threads: int = 10,
        status_codes: str | None = None,
        extra: list[str] | None = None,
    ) -> list[str]:
        # -q 安静模式（不输出横幅/进度）；-z 不显示进度；--no-error 抑制逐条错误
        args = ["dir", "-u", url, "-w", wordlist, "-q", "-z", "--no-error", "-t", str(threads)]
        if extensions:
            args += ["-x", extensions]
        if status_codes:
            args += ["-s", status_codes, "-b", ""]  # 自定义白名单时清空黑名单
        if extra:
            args += extra
        return args

    # ------------------------------------------------------------------ #
    def scan(
        self, url: str, *, wordlist: str | None = None, timeout: float = 900.0, **kw
    ) -> tuple[ToolResult, list[Finding]]:
        self.scope.check(url)
        tmp_path: str | None = None
        try:
            if not wordlist:
                fd, tmp_path = tempfile.mkstemp(prefix="sectoolkit_wl_", suffix=".txt")
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    fh.write("\n".join(pl.COMMON_PATHS))
                wordlist = tmp_path
            args = self.build_args(url, wordlist, **kw)
            result = self.tool.run(args, timeout=timeout)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
        return result, self.parse_output(result.stdout, url)

    # ------------------------------------------------------------------ #
    @staticmethod
    def parse_output(text: str, base_url: str) -> list[Finding]:
        findings: list[Finding] = []
        root = base_url.rstrip("/")
        for line in text.splitlines():
            m = _LINE_RE.match(line.strip())
            if not m:
                continue
            path, status, size = m.group(1), int(m.group(2)), int(m.group(3))
            sev = Severity.LOW if status < 400 else Severity.INFO
            findings.append(Finding(
                title=f"发现路径 {path} (HTTP {status})",
                target=root + (path if path.startswith("/") else "/" + path),
                severity=sev, source="gobuster",
                detail=f"状态码 {status}，大小 {size} 字节",
                evidence={"path": path, "status": status, "size": size},
                tags=["path", "recon"],
            ))
        return findings
