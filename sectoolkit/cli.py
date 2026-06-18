# -*- coding: utf-8 -*-
"""
sectoolkit 命令行入口。

子命令：

* ``fuzz``     —— HTTP 模糊测试（FUZZ 标记 / 单参数 / 目录探测）与本地字节变异。
* ``scan``     —— 调用 nmap / sqlmap 进行扫描。
* ``pentest``  —— 自动化渗透测试流水线。

全局授权参数（主动扫描必需）：

* ``--scope HOST[,HOST...]`` 或 ``--scope-file PATH``：授权目标范围。
* ``--authorize``：确认"我已获得对上述目标的书面测试授权"。

不带 ``--authorize`` 或未配置范围时，所有主动操作都会被拒绝（默认拒绝）。
"""

from __future__ import annotations

import argparse
import sys

from .http_client import HttpClient, backend_name
from .reporting import Report
from .scope import ScopeError, ScopeGuard

BANNER = r"""
  ___ ___ ___ _____ ___   ___  _    _  _____ _____
 / __| __/ __|_   _/ _ \ / _ \| |  | |/ /_ _|_   _|
 \__ \ _| (__  | || (_) | (_) | |__| ' < | |  | |
 |___/___\___| |_| \___/ \___/|____|_|\_\___| |_|
        授权安全测试工具包 v0.1 —— 仅限合法授权使用
"""


# --------------------------------------------------------------------------- #
# 通用
# --------------------------------------------------------------------------- #
def build_scope(args) -> ScopeGuard:
    if getattr(args, "scope_file", None):
        guard = ScopeGuard.from_file(args.scope_file, acknowledged=args.authorize)
    else:
        entries: list[str] = []
        for chunk in (args.scope or []):
            entries.extend(p.strip() for p in chunk.split(",") if p.strip())
        guard = ScopeGuard.from_entries(entries, acknowledged=args.authorize)
    return guard


def eprint(*args, **kw) -> None:
    """进度/状态信息一律打到 stderr，保持 stdout 只输出纯报告内容。"""
    kw.setdefault("file", sys.stderr)
    print(*args, **kw)


def emit_report(report: Report, args) -> None:
    fmt = args.format
    if args.output:
        report.write(args.output, fmt=fmt)
        eprint(f"\n[+] 报告已写入 {args.output}（格式: {fmt}）")
    else:
        if fmt == "json":
            print(report.to_json())
        elif fmt in ("md", "markdown"):
            print(report.to_markdown())
        elif fmt == "html":
            print(report.to_html())
    counts = report.counts()
    eprint("\n概览: " + " · ".join(f"{k}={v}" for k, v in counts.items() if v))


def make_client(args) -> HttpClient:
    return HttpClient(
        timeout=args.timeout,
        proxy=args.proxy,
        verify=not args.insecure,
        allow_redirects=args.follow_redirects,
    )


# --------------------------------------------------------------------------- #
# fuzz
# --------------------------------------------------------------------------- #
def cmd_fuzz(args) -> int:
    from .fuzzer import HttpFuzzer, Mutator, payloads as pl

    # 本地字节变异模式：不发网络流量，无需授权范围
    if args.mutate_seed is not None:
        return _run_mutate(args)

    scope = build_scope(args)
    try:
        scope.check(args.url)
    except ScopeError as exc:
        print(f"[拒绝] {exc}", file=sys.stderr)
        return 2

    client = make_client(args)
    fuzzer = HttpFuzzer(scope, client=client, threads=args.threads, delay=args.delay)

    if args.wordlist:
        payload_list = pl.load_wordlist(args.wordlist)
    else:
        payload_list = pl.get_category(args.category)

    report = Report(title="Fuzz 报告", target_summary=args.url)
    report.meta["http_backend"] = backend_name()

    if args.dirbust:
        words = pl.load_wordlist(args.wordlist) if args.wordlist else pl.COMMON_PATHS
        results = fuzzer.dirbust(args.url, words, method=args.method)
    elif args.param:
        results = fuzzer.fuzz_param(args.url, args.param, payload_list, method=args.method)
    else:
        if "FUZZ" not in args.url and not (args.data and "FUZZ" in args.data):
            print("[!] 未发现 FUZZ 标记。请在 URL 或 --data 中放置 FUZZ，"
                  "或改用 --param / --dirbust。", file=sys.stderr)
            return 2
        results = fuzzer.fuzz(
            args.url, payload_list, method=args.method, data=args.data,
        )

    report.extend(fuzzer.to_findings(results))
    interesting = [r for r in results if r.interesting]
    eprint(f"[+] 共发送 {len(results)} 个请求，{len(interesting)} 个出现异常。")
    emit_report(report, args)
    return 0


def _run_mutate(args) -> int:
    from .fuzzer import Mutator
    import os

    with open(args.mutate_seed, "rb") as fh:
        seed = fh.read()
    mut = Mutator(seed=args.seed)
    out_dir = args.mutate_out or "fuzz_cases"
    os.makedirs(out_dir, exist_ok=True)
    n = 0
    for i, case in enumerate(mut.generate(seed, args.count, max_rounds=args.max_rounds)):
        path = os.path.join(out_dir, f"case_{i:06d}.bin")
        with open(path, "wb") as fh:
            fh.write(case)
        n += 1
    print(f"[+] 已基于种子 {args.mutate_seed}（{len(seed)} 字节）生成 {n} 个变异样本 → {out_dir}/")
    print("    可配合崩溃监控运行目标程序，例如：")
    print(f"      for f in {out_dir}/*.bin; do ./target \"$f\" || echo \"CRASH: $f\"; done")
    return 0


# --------------------------------------------------------------------------- #
# scan
# --------------------------------------------------------------------------- #
def cmd_scan(args) -> int:
    from .tools import NmapScanner, SqlmapScanner

    scope = build_scope(args)
    report = Report(title=f"{args.tool} 扫描报告", target_summary=args.target)

    try:
        if args.tool == "nmap":
            scanner = NmapScanner(scope)
            if not scanner.available():
                print("[!] 未检测到 nmap。请先安装：`apt install nmap` / `brew install nmap`。",
                      file=sys.stderr)
                return 3
            result, findings = scanner.scan(
                args.target, ports=args.ports, service_detection=not args.no_sv,
                scan_type=args.scan_type, timing=args.timing, scripts=args.scripts,
            )
        else:  # sqlmap
            scanner = SqlmapScanner(scope)
            if not scanner.available():
                print("[!] 未检测到 sqlmap。安装：`pip install sqlmap` 或发行版包。",
                      file=sys.stderr)
                return 3
            result, findings = scanner.scan(
                args.target, data=args.data, level=args.level, risk=args.risk,
            )
    except ScopeError as exc:
        print(f"[拒绝] {exc}", file=sys.stderr)
        return 2

    report.extend(findings)
    if args.show_raw:
        eprint("----- 原始输出 -----")
        eprint(result.stdout[-4000:])
        eprint("--------------------")
    emit_report(report, args)
    return 0


# --------------------------------------------------------------------------- #
# pentest
# --------------------------------------------------------------------------- #
def cmd_pentest(args) -> int:
    from .pentest import Orchestrator, PentestConfig

    scope = build_scope(args)
    try:
        scope.check(args.target)
    except ScopeError as exc:
        print(f"[拒绝] {exc}", file=sys.stderr)
        return 2

    cfg = PentestConfig(
        do_portscan=not args.no_portscan,
        do_dirbust=not args.no_dirbust,
        do_param_fuzz=not args.no_fuzz,
        do_sqlmap=not args.no_sqlmap,
        ports=args.ports,
        fuzz_params=[p for p in (args.param or [])],
        threads=args.threads,
        delay=args.delay,
    )
    orch = Orchestrator(scope, config=cfg, client=make_client(args))
    report = orch.run(args.target, log=eprint)
    emit_report(report, args)
    return 0


# --------------------------------------------------------------------------- #
# parser
# --------------------------------------------------------------------------- #
def add_scope_args(p: argparse.ArgumentParser) -> None:
    g = p.add_argument_group("授权范围（主动扫描必需）")
    g.add_argument("--scope", action="append", metavar="HOST",
                   help="授权目标，可逗号分隔或多次指定（支持 IP/CIDR/域名/*.域名）")
    g.add_argument("--scope-file", help="从文件读取授权范围（每行一条）")
    g.add_argument("--authorize", action="store_true",
                   help="确认你已获得对上述目标的书面测试授权（不加则拒绝执行）")


def add_output_args(p: argparse.ArgumentParser) -> None:
    g = p.add_argument_group("输出")
    g.add_argument("-o", "--output", help="报告输出文件路径")
    g.add_argument("-f", "--format", choices=["json", "md", "markdown", "html"],
                   default="json", help="报告格式（默认 json）")


def add_http_args(p: argparse.ArgumentParser) -> None:
    g = p.add_argument_group("HTTP")
    g.add_argument("--timeout", type=float, default=10.0, help="单请求超时秒数")
    g.add_argument("--proxy", help="HTTP 代理，如 http://127.0.0.1:8080")
    g.add_argument("--insecure", action="store_true", help="不校验 TLS 证书")
    g.add_argument("--follow-redirects", action="store_true", help="跟随重定向")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sectoolkit",
        description="授权安全测试工具包：模糊测试 / 自动化渗透 / 外部工具调用。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="⚠ 仅限对你拥有或已获书面授权的目标使用。未授权扫描可能违法。",
    )
    parser.add_argument("--no-banner", action="store_true", help="不打印横幅")
    sub = parser.add_subparsers(dest="command", required=True)

    # ---- fuzz ---- #
    pf = sub.add_parser("fuzz", help="HTTP 模糊测试 / 本地字节变异")
    pf.add_argument("url", nargs="?", help="目标 URL（可含 FUZZ 标记）")
    pf.add_argument("-X", "--method", default="GET", help="HTTP 方法")
    pf.add_argument("-d", "--data", help="请求体（可含 FUZZ 标记）")
    pf.add_argument("--param", help="对指定查询参数注入载荷")
    pf.add_argument("--dirbust", action="store_true", help="目录/路径探测模式")
    pf.add_argument("-c", "--category",
                    default="all",
                    help="载荷类别: sqli/xss/traversal/cmdi/ssti/lfi/generic/all")
    pf.add_argument("-w", "--wordlist", help="自定义载荷/词表文件")
    pf.add_argument("-t", "--threads", type=int, default=10, help="并发线程数")
    pf.add_argument("--delay", type=float, default=0.0, help="每请求后限速秒数")
    # 本地字节变异
    pf.add_argument("--mutate-seed", help="本地字节变异：种子文件路径（此模式不发网络流量）")
    pf.add_argument("--count", type=int, default=100, help="变异样本数量")
    pf.add_argument("--max-rounds", type=int, default=3, help="单样本最大变异轮数")
    pf.add_argument("--seed", type=int, default=0, help="随机种子（可复现）")
    pf.add_argument("--mutate-out", help="变异样本输出目录（默认 fuzz_cases/）")
    add_scope_args(pf)
    add_http_args(pf)
    add_output_args(pf)
    pf.set_defaults(func=cmd_fuzz)

    # ---- scan ---- #
    ps = sub.add_parser("scan", help="调用 nmap / sqlmap 扫描")
    ps.add_argument("tool", choices=["nmap", "sqlmap"], help="要调用的工具")
    ps.add_argument("target", help="目标 host / IP / URL")
    ps.add_argument("--ports", help="[nmap] 端口范围，如 1-1000 或 22,80,443")
    ps.add_argument("--scan-type", choices=["connect", "syn"], default="connect",
                    help="[nmap] 扫描方式（syn 需 root）")
    ps.add_argument("--timing", type=int, default=3, help="[nmap] 时序模板 0-5")
    ps.add_argument("--no-sv", action="store_true", help="[nmap] 关闭服务版本探测")
    ps.add_argument("--scripts", help="[nmap] --script 值，如 default,vuln")
    ps.add_argument("--data", help="[sqlmap] POST 数据")
    ps.add_argument("--level", type=int, default=1, help="[sqlmap] 检测等级 1-5")
    ps.add_argument("--risk", type=int, default=1, help="[sqlmap] 风险等级 1-3")
    ps.add_argument("--show-raw", action="store_true", help="附带打印工具原始输出")
    add_scope_args(ps)
    add_output_args(ps)
    ps.set_defaults(func=cmd_scan)

    # ---- pentest ---- #
    pp = sub.add_parser("pentest", help="自动化渗透测试流水线")
    pp.add_argument("target", help="目标 host / IP / URL")
    pp.add_argument("--ports", help="[nmap] 端口范围")
    pp.add_argument("--param", action="append", help="要 fuzz 的查询参数（可多次）")
    pp.add_argument("-t", "--threads", type=int, default=10, help="并发线程数")
    pp.add_argument("--delay", type=float, default=0.0, help="每请求后限速秒数")
    pp.add_argument("--no-portscan", action="store_true", help="跳过 nmap 端口扫描")
    pp.add_argument("--no-dirbust", action="store_true", help="跳过目录探测")
    pp.add_argument("--no-fuzz", action="store_true", help="跳过参数 fuzz")
    pp.add_argument("--no-sqlmap", action="store_true", help="跳过 sqlmap 验证")
    add_scope_args(pp)
    add_http_args(pp)
    add_output_args(pp)
    pp.set_defaults(func=cmd_pentest)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "no_banner", False):
        print(BANNER, file=sys.stderr)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\n[中断] 用户取消。", file=sys.stderr)
        return 130
    except (ScopeError, FileNotFoundError, KeyError, ValueError) as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
