# -*- coding: utf-8 -*-
"""
外部工具封装基类。

安全要点：

* **绝不使用 shell=True**：所有命令以参数列表（list[str]）方式执行，避免命令注入。
* **可用性检测**：``shutil.which`` 找不到可执行文件时抛出明确的 :class:`ToolNotFound`，
  而不是让脚本崩在一堆 traceback 里。
* **超时控制**：``subprocess.run(timeout=...)`` 防止扫描挂死。
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field


class ToolNotFound(RuntimeError):
    """目标可执行文件未安装时抛出。"""


@dataclass
class ToolResult:
    args: list[str]
    returncode: int
    stdout: str
    stderr: str
    duration: float
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out


@dataclass
class ExternalTool:
    """通用外部命令封装。"""

    binary: str
    extra_env: dict = field(default_factory=dict)

    def available(self) -> bool:
        return shutil.which(self.binary) is not None

    def resolved_path(self) -> str | None:
        return shutil.which(self.binary)

    def ensure_available(self) -> None:
        if not self.available():
            raise ToolNotFound(
                f"未找到可执行文件 {self.binary!r}。请先安装（例如 nmap: `apt install nmap`，"
                f"sqlmap: `pip install sqlmap` 或发行版包管理器），并确保它在 PATH 中。"
            )

    def run(self, args: list[str], *, timeout: float = 600.0, input_text: str | None = None) -> ToolResult:
        """以参数列表方式执行 ``[binary, *args]``。"""
        import os
        import time

        self.ensure_available()
        cmd = [self.binary, *args]
        env = {**os.environ, **self.extra_env} if self.extra_env else None
        t0 = time.perf_counter()
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                input=input_text,
                env=env,
                check=False,
            )
            return ToolResult(
                args=cmd, returncode=proc.returncode,
                stdout=proc.stdout or "", stderr=proc.stderr or "",
                duration=time.perf_counter() - t0,
            )
        except subprocess.TimeoutExpired as exc:
            return ToolResult(
                args=cmd, returncode=-1,
                stdout=(exc.stdout or b"").decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or ""),
                stderr=f"超时（>{timeout}s）", duration=timeout, timed_out=True,
            )

    def version(self) -> str:
        """尽力获取版本信息（失败返回空串）。"""
        for flag in ("--version", "-V", "version"):
            try:
                res = self.run([flag], timeout=15)
                if res.stdout.strip():
                    return res.stdout.strip().splitlines()[0]
            except Exception:  # noqa: BLE001
                continue
        return ""
