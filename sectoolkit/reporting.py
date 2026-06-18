# -*- coding: utf-8 -*-
"""
统一的发现（Finding）与报告（Report）数据结构，支持 JSON / Markdown / HTML 输出。

各模块（fuzzer、tools、pentest）都把结果归一化成 :class:`Finding`，再由
:class:`Report` 汇总输出，方便后续二次处理或归档。
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import html
import json
from dataclasses import dataclass, field
from enum import IntEnum


class Severity(IntEnum):
    INFO = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

    @classmethod
    def parse(cls, value: "str | int | Severity") -> "Severity":
        if isinstance(value, Severity):
            return value
        if isinstance(value, int):
            return cls(value)
        return cls.__members__[str(value).strip().upper()]

    def __str__(self) -> str:  # noqa: D105
        return self.name


@dataclass
class Finding:
    """一条安全发现 / 观测结果。"""

    title: str
    target: str
    severity: Severity = Severity.INFO
    source: str = ""          # 产生该发现的模块/工具，如 "nmap"、"fuzzer"
    detail: str = ""
    evidence: dict = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: dt.datetime.now().isoformat(timespec="seconds"))

    def to_dict(self) -> dict:
        data = dataclasses.asdict(self)
        data["severity"] = str(self.severity)
        return data


@dataclass
class Report:
    """一次任务的完整结果集合。"""

    title: str = "sectoolkit 报告"
    target_summary: str = ""
    findings: list[Finding] = field(default_factory=list)
    meta: dict = field(default_factory=dict)
    started: str = field(default_factory=lambda: dt.datetime.now().isoformat(timespec="seconds"))

    def add(self, finding: Finding) -> Finding:
        self.findings.append(finding)
        return finding

    def extend(self, findings: "list[Finding]") -> None:
        self.findings.extend(findings)

    def sorted_findings(self) -> list[Finding]:
        return sorted(self.findings, key=lambda f: int(f.severity), reverse=True)

    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {s.name: 0 for s in Severity}
        for f in self.findings:
            out[f.severity.name] += 1
        return out

    # ----------------------------- 输出 ------------------------------ #
    def to_json(self, *, indent: int = 2) -> str:
        payload = {
            "title": self.title,
            "started": self.started,
            "generated": dt.datetime.now().isoformat(timespec="seconds"),
            "target_summary": self.target_summary,
            "meta": self.meta,
            "counts": self.counts(),
            "findings": [f.to_dict() for f in self.sorted_findings()],
        }
        return json.dumps(payload, ensure_ascii=False, indent=indent)

    def to_markdown(self) -> str:
        lines = [
            f"# {self.title}",
            "",
            f"- 开始时间：{self.started}",
            f"- 生成时间：{dt.datetime.now().isoformat(timespec='seconds')}",
            f"- 目标：{self.target_summary or '(未记录)'}",
            "",
            "## 概览",
            "",
            "| 级别 | 数量 |",
            "| --- | --- |",
        ]
        for name, n in self.counts().items():
            lines.append(f"| {name} | {n} |")
        lines += ["", "## 详细发现", ""]
        if not self.findings:
            lines.append("（无发现）")
        for i, f in enumerate(self.sorted_findings(), 1):
            lines.append(f"### {i}. [{f.severity}] {f.title}")
            lines.append("")
            lines.append(f"- 目标：`{f.target}`")
            lines.append(f"- 来源：{f.source or '-'}")
            if f.tags:
                lines.append(f"- 标签：{', '.join(f.tags)}")
            if f.detail:
                lines.append(f"- 说明：{f.detail}")
            if f.evidence:
                lines.append("- 证据：")
                lines.append("")
                lines.append("```json")
                lines.append(json.dumps(f.evidence, ensure_ascii=False, indent=2))
                lines.append("```")
            lines.append("")
        return "\n".join(lines)

    def to_html(self) -> str:
        colors = {
            "INFO": "#6b7280", "LOW": "#2563eb", "MEDIUM": "#d97706",
            "HIGH": "#dc2626", "CRITICAL": "#7c2d12",
        }
        rows = []
        for f in self.sorted_findings():
            color = colors.get(f.severity.name, "#6b7280")
            ev = html.escape(json.dumps(f.evidence, ensure_ascii=False, indent=2)) if f.evidence else ""
            rows.append(
                f"<tr>"
                f"<td><span style='color:#fff;background:{color};padding:2px 8px;"
                f"border-radius:4px'>{f.severity}</span></td>"
                f"<td>{html.escape(f.title)}</td>"
                f"<td><code>{html.escape(f.target)}</code></td>"
                f"<td>{html.escape(f.source)}</td>"
                f"<td>{html.escape(f.detail)}<pre>{ev}</pre></td>"
                f"</tr>"
            )
        counts = " · ".join(f"{k}:{v}" for k, v in self.counts().items())
        return f"""<!doctype html>
<html lang="zh"><head><meta charset="utf-8">
<title>{html.escape(self.title)}</title>
<style>
body{{font-family:-apple-system,Segoe UI,Roboto,sans-serif;margin:2rem;color:#111}}
table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #e5e7eb;padding:8px;text-align:left;vertical-align:top}}
th{{background:#f9fafb}} pre{{white-space:pre-wrap;margin:.3rem 0 0;font-size:12px;color:#374151}}
.meta{{color:#6b7280}}
</style></head><body>
<h1>{html.escape(self.title)}</h1>
<p class="meta">开始 {self.started} · 目标 {html.escape(self.target_summary or '-')}</p>
<p>概览：{html.escape(counts)}</p>
<table><thead><tr><th>级别</th><th>标题</th><th>目标</th><th>来源</th><th>详情</th></tr></thead>
<tbody>{''.join(rows) or '<tr><td colspan=5>（无发现）</td></tr>'}</tbody></table>
</body></html>"""

    def write(self, path: str, *, fmt: str = "json") -> None:
        fmt = fmt.lower()
        if fmt == "json":
            text = self.to_json()
        elif fmt in ("md", "markdown"):
            text = self.to_markdown()
        elif fmt == "html":
            text = self.to_html()
        else:
            raise ValueError(f"不支持的报告格式：{fmt}")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
