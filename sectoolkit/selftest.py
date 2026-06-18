# -*- coding: utf-8 -*-
"""
sectoolkit 离线自测。

只测试不依赖外部工具 / 网络的纯逻辑部分：授权范围、变异器、载荷、报告、
nmap XML 解析、sqlmap 输出解析。可直接运行：

    python sectoolkit/selftest.py
"""

from __future__ import annotations

import os
import sys

# 允许从仓库根目录或包内直接运行
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json  # noqa: E402

from sectoolkit.fuzzer import Mutator, parse_raw_request, payloads as pl  # noqa: E402
from sectoolkit.reporting import Finding, Report, Severity  # noqa: E402
from sectoolkit.scope import ScopeError, ScopeGuard  # noqa: E402
from sectoolkit.tools.gobuster import GobusterScanner  # noqa: E402
from sectoolkit.tools.nmap import NmapScanner  # noqa: E402
from sectoolkit.tools.nuclei import NucleiScanner  # noqa: E402
from sectoolkit.tools.sqlmap import SqlmapScanner  # noqa: E402

_passed = 0
_failed = 0


def check(name: str, cond: bool) -> None:
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  ✓ {name}")
    else:
        _failed += 1
        print(f"  ✗ {name}")


def test_scope() -> None:
    print("[scope] 授权范围")
    g = ScopeGuard.from_entries(
        ["10.0.0.0/24", "app.example.com", "*.lab.example.com", "192.168.1.5"],
        acknowledged=True,
    )
    check("CIDR 命中", g.allows("10.0.0.55"))
    check("CIDR 未命中", not g.allows("10.0.1.1"))
    check("精确域名命中", g.allows("http://app.example.com/x?a=1"))
    check("通配子域命中", g.allows("a.b.lab.example.com"))
    check("通配不含裸域", not g.allows("lab.example.com") or "lab.example.com" in g.wildcards)
    check("范围外被拒", not g.allows("evil.com"))
    check("单 IP 命中", g.allows("192.168.1.5:8080"))

    # 默认拒绝：未确认授权
    g2 = ScopeGuard.from_entries(["10.0.0.0/24"], acknowledged=False)
    raised = False
    try:
        g2.check("10.0.0.5")
    except ScopeError:
        raised = True
    check("未授权 → 拒绝", raised)

    # 默认拒绝：空范围
    g3 = ScopeGuard(acknowledged=True)
    raised = False
    try:
        g3.check("10.0.0.5")
    except ScopeError:
        raised = True
    check("空范围 → 拒绝", raised)

    # 范围内放行
    check("授权 + 范围内 → 返回 host", g.check("10.0.0.9") == "10.0.0.9")


def test_mutator() -> None:
    print("[mutator] 字节变异器")
    seed = b"GET /index.html HTTP/1.1\r\nHost: example\r\n\r\n"
    m1 = Mutator(seed=42)
    m2 = Mutator(seed=42)
    cases1 = list(m1.generate(seed, 50))
    cases2 = list(m2.generate(seed, 50))
    check("生成数量正确", len(cases1) == 50)
    check("相同 seed 可复现", cases1 == cases2)
    different = sum(1 for c in cases1 if c != seed)
    check("产生了变异（≥90% 不同于种子）", different >= 45)
    m3 = Mutator(seed=7)
    cases3 = list(m3.generate(seed, 50))
    check("不同 seed → 不同序列", cases1 != cases3)
    # 空种子不应崩溃
    check("空种子不崩溃", isinstance(Mutator(seed=1).mutate(b"", rounds=3), bytes))


def test_payloads() -> None:
    print("[payloads] 载荷与特征库")
    check("sqli 类别非空", len(pl.get_category("sqli")) > 0)
    allp = pl.get_category("all")
    check("all 合并各类别", len(allp) >= sum(len(v) for v in pl.CATEGORIES.values()))
    check("SQL 报错特征识别", pl.has_sql_error("...You have an error in your SQL syntax...") is not None)
    check("正常文本无误报", pl.has_sql_error("welcome home") is None)
    raised = False
    try:
        pl.get_category("nope")
    except KeyError:
        raised = True
    check("未知类别报错", raised)


def test_reporting() -> None:
    print("[reporting] 报告")
    rep = Report(title="T", target_summary="127.0.0.1")
    rep.add(Finding("高危项", "127.0.0.1", Severity.HIGH, "nmap", "x"))
    rep.add(Finding("信息项", "127.0.0.1", Severity.INFO, "fuzzer"))
    check("计数正确", rep.counts()["HIGH"] == 1 and rep.counts()["INFO"] == 1)
    check("按级别排序", rep.sorted_findings()[0].severity == Severity.HIGH)
    j = rep.to_json()
    check("JSON 含中文且可读", '"HIGH"' in j and "高危项" in j)
    check("Markdown 输出", rep.to_markdown().startswith("# T"))
    check("HTML 输出", "<table>" in rep.to_html())
    check("Severity.parse 字符串", Severity.parse("high") == Severity.HIGH)


def test_nmap_parse() -> None:
    print("[nmap] XML 解析")
    xml = """<?xml version="1.0"?><nmaprun>
    <host><address addr="127.0.0.1" addrtype="ipv4"/>
      <hostnames><hostname name="localhost"/></hostnames>
      <ports>
        <port protocol="tcp" portid="22"><state state="open"/>
          <service name="ssh" product="OpenSSH" version="8.9"/></port>
        <port protocol="tcp" portid="3306"><state state="open"/>
          <service name="mysql"/></port>
        <port protocol="tcp" portid="81"><state state="closed"/>
          <service name="hosts2-ns"/></port>
      </ports></host></nmaprun>"""
    findings = NmapScanner.parse_xml(xml)
    check("仅解析 open 端口（2 个）", len(findings) == 2)
    titles = " ".join(f.title for f in findings)
    check("含 22/ssh", "22/tcp ssh" in titles)
    check("mysql(3306) 标为 MEDIUM", any(
        f.evidence.get("port") == "3306" and f.severity == Severity.MEDIUM for f in findings))
    check("提取版本信息", any(f.evidence.get("version") == "8.9" for f in findings))
    # 通过实例方法提取端口号
    scanner = NmapScanner(ScopeGuard(acknowledged=True))
    check("open_ports 提取", scanner.open_ports(findings) == [22, 3306])
    check("坏 XML 不崩溃", NmapScanner.parse_xml("<not xml") == [])


def test_sqlmap_parse() -> None:
    print("[sqlmap] 输出解析")
    vuln = ("GET parameter 'id' is vulnerable. Do you want to keep testing?\n"
            "sqlmap identified the following injection point(s) with a total ...:\n"
            "---\n"
            "Parameter: id (GET)\n"
            "    Type: boolean-based blind\n"
            "---\n"
            "back-end DBMS: MySQL >= 5.0")
    f = SqlmapScanner.parse_output(vuln, "http://t/x?id=1")
    check("识别注入点", len(f) == 1 and f[0].severity == Severity.CRITICAL)
    check("提取参数名", "id" in f[0].evidence.get("injectable_params", []))
    check("提取 DBMS", "MySQL" in f[0].evidence.get("dbms", ""))
    safe = "all tested parameters do not appear to be injectable"
    f2 = SqlmapScanner.parse_output(safe, "http://t/x?id=1")
    check("无注入 → INFO", len(f2) == 1 and f2[0].severity == Severity.INFO)


def test_nuclei_parse() -> None:
    print("[nuclei] JSONL 解析")
    good = json.dumps({
        "template-id": "exposed-panel",
        "info": {"name": "Admin Panel", "severity": "high", "tags": ["panel"]},
        "type": "http", "host": "http://t", "matched-at": "http://t/admin",
    })
    findings = NucleiScanner.parse_jsonl(good + "\nnot json line\n{broken")
    check("仅解析有效行（忽略坏行）", len(findings) == 1)
    check("severity 映射 high", findings[0].severity == Severity.HIGH)
    check("标题含模板名", "Admin Panel" in findings[0].title)
    check("matched-at 作为目标", findings[0].target == "http://t/admin")
    check("提取 tags", "panel" in findings[0].tags)
    check("空输入返回空", NucleiScanner.parse_jsonl("") == [])


def test_gobuster_parse() -> None:
    print("[gobuster] 输出解析")
    out = ("/admin                (Status: 301) [Size: 312] [--> /admin/]\n"
           "/login                (Status: 200) [Size: 1234]\n"
           "garbage line without status\n")
    findings = GobusterScanner.parse_output(out, "http://t")
    check("解析 2 条命中", len(findings) == 2)
    check("URL 拼接正确", any(f.target == "http://t/admin" for f in findings))
    check("提取状态码/大小", any(
        f.evidence.get("status") == 200 and f.evidence.get("size") == 1234 for f in findings))


def test_raw_request() -> None:
    print("[request] 原始请求解析")
    raw = ("POST /login?x=1 HTTP/1.1\r\n"
           "Host: app.example.com\r\n"
           "Content-Type: application/x-www-form-urlencoded\r\n"
           "Content-Length: 999\r\n"
           "\r\n"
           "user=admin&pass=FUZZ")
    req = parse_raw_request(raw, scheme="https")
    check("方法解析", req.method == "POST")
    check("URL 由 Host+target 推导", req.url == "https://app.example.com/login?x=1")
    lower_keys = {k.lower() for k in req.headers}
    check("丢弃 Content-Length", "content-length" not in lower_keys)
    check("保留 Content-Type", req.headers.get("Content-Type") == "application/x-www-form-urlencoded")
    check("body 提取含 FUZZ", req.body == "user=admin&pass=FUZZ")

    req2 = parse_raw_request("GET http://h/x HTTP/1.1\nHost: h\n\n")
    check("绝对 URL target 直接采用", req2.url == "http://h/x")

    raised = False
    try:
        parse_raw_request("GET /x HTTP/1.1\n\n")  # 相对路径且无 Host
    except ValueError:
        raised = True
    check("缺 Host + 相对路径 → 报错", raised)


def main() -> int:
    print("=" * 56)
    print("sectoolkit 离线自测")
    print("=" * 56)
    for fn in (test_scope, test_mutator, test_payloads, test_reporting,
               test_nmap_parse, test_sqlmap_parse, test_nuclei_parse,
               test_gobuster_parse, test_raw_request):
        fn()
    print("-" * 56)
    print(f"通过 {_passed} / {_passed + _failed}")
    return 0 if _failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
