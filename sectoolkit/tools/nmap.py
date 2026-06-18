# -*- coding: utf-8 -*-
"""
nmap 封装：构造命令、执行、解析 XML 输出为统一的 :class:`Finding`。

通过 ``-oX -`` 让 nmap 把 XML 结果打到 stdout，再用标准库 ``xml.etree``
解析，无需额外依赖。所有目标在执行前都经过 ScopeGuard 校验。
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass

from ..reporting import Finding, Severity
from ..scope import ScopeGuard
from .base import ExternalTool, ToolResult


@dataclass
class NmapScanner:
    scope: ScopeGuard
    binary: str = "nmap"

    def __post_init__(self) -> None:
        self.tool = ExternalTool(self.binary)

    def available(self) -> bool:
        return self.tool.available()

    # ------------------------------------------------------------------ #
    def build_args(
        self,
        target: str,
        *,
        ports: str | None = None,
        service_detection: bool = True,
        scan_type: str = "connect",   # connect=-sT（无需 root），syn=-sS
        timing: int = 3,
        scripts: str | None = None,
        extra: list[str] | None = None,
    ) -> list[str]:
        args: list[str] = ["-oX", "-", f"-T{timing}"]
        args.append("-sS" if scan_type == "syn" else "-sT")
        if service_detection:
            args.append("-sV")
        if ports:
            args += ["-p", ports]
        if scripts:
            args += ["--script", scripts]
        if extra:
            args += extra
        args.append(target)
        return args

    # ------------------------------------------------------------------ #
    def scan(self, target: str, *, timeout: float = 900.0, **kw) -> tuple[ToolResult, list[Finding]]:
        """对单个目标执行扫描，返回 (原始结果, 解析后的发现列表)。"""
        host = self.scope.check(target)
        args = self.build_args(host, **kw)
        result = self.tool.run(args, timeout=timeout)
        findings = self.parse_xml(result.stdout) if result.stdout.strip().startswith("<") else []
        if not result.ok and not findings:
            findings.append(
                Finding(
                    title="nmap 执行未成功",
                    target=host, severity=Severity.INFO, source="nmap",
                    detail=(result.stderr or "无输出").strip()[:500],
                )
            )
        return result, findings

    # ------------------------------------------------------------------ #
    @staticmethod
    def parse_xml(xml_text: str) -> list[Finding]:
        """解析 nmap XML，把每个开放端口转成一条 Finding。"""
        findings: list[Finding] = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return findings

        for host in root.findall("host"):
            addr_el = host.find("address")
            address = addr_el.get("addr") if addr_el is not None else "?"
            hostname_el = host.find("hostnames/hostname")
            hostname = hostname_el.get("name") if hostname_el is not None else ""
            label = f"{address}" + (f" ({hostname})" if hostname else "")

            for port in host.findall("ports/port"):
                state_el = port.find("state")
                state = state_el.get("state") if state_el is not None else ""
                if state != "open":
                    continue
                portid = port.get("portid")
                proto = port.get("protocol")
                svc = port.find("service")
                svc_name = svc.get("name", "") if svc is not None else ""
                product = svc.get("product", "") if svc is not None else ""
                version = svc.get("version", "") if svc is not None else ""
                svc_desc = " ".join(x for x in (product, version) if x).strip()

                # 一些"高暴露面"端口给更高的关注级别
                risky = {"21", "23", "445", "3389", "3306", "5432", "6379", "27017", "9200"}
                sev = Severity.MEDIUM if portid in risky else Severity.INFO

                findings.append(
                    Finding(
                        title=f"开放端口 {portid}/{proto} {svc_name}".strip(),
                        target=label,
                        severity=sev,
                        source="nmap",
                        detail=f"服务: {svc_name or '未知'}" + (f" | {svc_desc}" if svc_desc else ""),
                        evidence={
                            "port": portid, "protocol": proto, "service": svc_name,
                            "product": product, "version": version,
                        },
                        tags=["port", "recon"],
                    )
                )
        return findings

    def open_ports(self, findings: list[Finding]) -> list[int]:
        ports: list[int] = []
        for f in findings:
            p = f.evidence.get("port")
            if p and str(p).isdigit():
                ports.append(int(p))
        return sorted(set(ports))
