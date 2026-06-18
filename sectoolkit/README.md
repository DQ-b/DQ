# sectoolkit —— 授权安全测试工具包

一个用纯 Python（标准库即可运行）实现的轻量级安全测试工具包，包含三块能力：

| 模块 | 能力 | 入口 |
| --- | --- | --- |
| `fuzzer` | **模糊测试**：HTTP 参数/路径/头部/原始请求 fuzz + 通用字节级变异 | `sectoolkit fuzz` |
| `tools` | **调用现有安全工具**：封装 nmap / sqlmap / nuclei / gobuster，解析结果为统一报告 | `sectoolkit scan` |
| `pentest` | **自动化渗透测试**：侦察→端口扫描→Web fuzz→nuclei→SQLi 验证 流水线 | `sectoolkit pentest` |

> ⚠️ **仅限合法授权使用。** 本工具会发送主动探测流量。请仅对你**拥有或已获得
> 书面授权**的目标使用。所有主动扫描都受授权范围（ScopeGuard）约束：默认拒绝，
> 必须同时提供 `--scope/--scope-file` 与 `--authorize` 才会执行。对未授权系统进行
> 扫描在多数司法辖区属于违法行为。

---

## 安装

核心功能零依赖（Python 3.9+）。可选增强：

```bash
pip install -r sectoolkit/requirements.txt   # 安装可选的 requests
# 外部工具需自行安装：
#   nmap   : apt install nmap   / brew install nmap
#   sqlmap : pip install sqlmap / 发行版包
```

运行方式（从仓库根目录）：

```bash
python -m sectoolkit --help
```

## 授权范围（必读）

任何主动扫描前都要声明授权范围，并显式确认授权：

```bash
# 方式一：命令行指定
python -m sectoolkit pentest http://127.0.0.1:8000 \
    --scope 127.0.0.1 --authorize

# 方式二：范围文件（推荐，便于审计）
python -m sectoolkit pentest staging.example.com \
    --scope-file sectoolkit/scope.example.txt --authorize
```

范围条目支持：精确 IP、CIDR（`10.0.0.0/24`）、精确域名、通配子域（`*.example.com`）。
**不在范围内的目标一律拒绝**；不加 `--authorize` 也一律拒绝。

---

## 1) 模糊测试 `fuzz`

**HTTP 模糊测试**——用 `FUZZ` 标记注入点，或指定参数/目录模式：

```bash
# 用 FUZZ 标记（可在 URL / --data / 头部中）
python -m sectoolkit fuzz "http://127.0.0.1:8000/item?id=FUZZ" \
    -c all --scope 127.0.0.1 --authorize

# 针对单个查询参数注入多类别载荷
python -m sectoolkit fuzz "http://127.0.0.1:8000/item?id=1" \
    --param id -c sqli --scope 127.0.0.1 --authorize

# 目录/路径探测（内置小词表，或 -w 指定 SecLists 等）
python -m sectoolkit fuzz http://127.0.0.1:8000 --dirbust \
    -w /path/to/wordlist.txt --scope 127.0.0.1 --authorize -f md
```

**原始请求 fuzz**——把 Burp/ZAP 里复制出来的原始 HTTP 请求存成文件，在注入点放
`FUZZ` 标记（可在请求行/头部/请求体任意位置），直接 fuzz：

```bash
# req.txt:
#   POST /login HTTP/1.1
#   Host: 127.0.0.1:8000
#   Content-Type: application/x-www-form-urlencoded
#
#   user=admin&pass=FUZZ
python -m sectoolkit fuzz --request req.txt -c sqli --scheme http \
    --scope 127.0.0.1 --authorize
```

URL 由 `Host` 头与请求行推导；发送时自动丢弃 `Content-Length`（按实际 body 重算）
与 `Accept-Encoding`（避免压缩影响差异分析）。授权校验同样针对请求里的目标主机。

引擎会建立**基线**并对每个响应做差异分析，自动标记：SQL 报错特征（疑似 SQLi）、
载荷原样反射（疑似 XSS）、5xx、状态码/长度显著偏离基线、超时等。

**本地字节变异**（不发网络流量，用于喂本地解析器/文件格式 fuzz，无需授权范围）：

```bash
python -m sectoolkit fuzz --mutate-seed sample.json \
    --count 500 --max-rounds 4 --mutate-out cases/
# 随后配合崩溃监控运行目标：
#   for f in cases/*.bin; do ./target "$f" || echo "CRASH: $f"; done
```

变异策略借鉴 AFL/radamsa：位翻转、字节翻转、算术增减、插入边界整数/魔法值、
块删除/复制、截断等。固定 `--seed` 可复现样本序列。

## 2) 调用现有工具 `scan`

```bash
# nmap：连接扫描 + 服务版本探测，结果解析为发现项
python -m sectoolkit scan nmap 127.0.0.1 \
    --ports 1-1000 --scan-type connect \
    --scope 127.0.0.1 --authorize -f md

# sqlmap：非交互检测某 URL 的注入点
python -m sectoolkit scan sqlmap "http://127.0.0.1:8000/item?id=1" \
    --level 2 --risk 1 --scope 127.0.0.1 --authorize

# nuclei：模板化漏洞扫描，按严重度过滤
python -m sectoolkit scan nuclei http://127.0.0.1:8000 \
    --severity medium,high,critical --scope 127.0.0.1 --authorize -f md

# gobuster：目录爆破（不带 -w 时用内置小词表，建议指定 SecLists）
python -m sectoolkit scan gobuster http://127.0.0.1:8000 \
    -w /path/to/wordlist.txt -x php,bak --scope 127.0.0.1 --authorize
```

工具未安装时会给出清晰提示并以非零退出码返回，而不是崩溃。命令以参数列表执行
（绝不 `shell=True`），避免命令注入。

## 3) 自动化渗透测试 `pentest`

把上面的能力串成一条流水线，输出汇总报告：

```bash
python -m sectoolkit pentest "http://127.0.0.1:8000/item?id=1" \
    --param id --scope 127.0.0.1 --authorize \
    -f html -o report.html
```

流程：`nmap 端口扫描 → 推导 Web 端口 → 目录探测 → nuclei 漏洞扫描 → 参数 fuzz →
sqlmap 验证`。任一外部工具缺失会自动跳过并在报告中记录，不中断流程。可用
`--no-portscan` / `--no-dirbust` / `--no-nuclei` / `--no-fuzz` / `--no-sqlmap`
裁剪步骤，`--nuclei-severity medium,high,critical` 控制 nuclei 噪声。

---

## 报告格式

`-f json|md|html`，配合 `-o FILE` 写文件；不指定 `-o` 时打印到 stdout。
所有结果都归一化为 `Finding`（级别 / 标题 / 目标 / 来源 / 证据），便于二次处理。

## 作为库使用

```python
from sectoolkit.scope import ScopeGuard
from sectoolkit.fuzzer import HttpFuzzer, payloads

scope = ScopeGuard.from_entries(["127.0.0.1"], acknowledged=True)
fuzzer = HttpFuzzer(scope)
results = fuzzer.fuzz_param("http://127.0.0.1:8000/item?id=1", "id",
                            payloads.get_category("sqli"))
for f in fuzzer.to_findings(results):
    print(f.severity, f.title, f.detail)
```

## 测试

```bash
python sectoolkit/selftest.py     # 离线自测（不依赖外部工具/网络）
```

## 本地练习靶场（安全演示）

仓库自带一个**故意留洞、只监听 `127.0.0.1`** 的练习靶场，可在本机安全地体验
全流程，不碰任何真实站点：

```bash
# 1) 启动靶场（另开一个终端）
python sectoolkit/examples/vulnerable_app.py --port 8799

# 2) 对它跑完整流水线并生成报告
python -m sectoolkit pentest "http://127.0.0.1:8799/item?id=1" --param id \
    --scope 127.0.0.1 --authorize -f html -o report.html
```

预期会看到：参数 fuzz 命中疑似 SQLi（`/item?id='` 触发 SQL 报错）与反射型 XSS、
目录探测命中 `/.env` `/admin` `/config` 等路径；未安装的 nmap/nuclei/sqlmap 会被
优雅跳过并记录在报告里。

## 目录结构

```
sectoolkit/
├── cli.py            # 命令行入口（fuzz / scan / pentest）
├── scope.py          # 授权范围闸门（默认拒绝）
├── reporting.py      # Finding / Report，JSON·MD·HTML 输出
├── http_client.py    # HTTP 封装（requests 优先，回退 urllib）
├── fuzzer/
│   ├── engine.py     # HTTP fuzz 引擎（并发 + 基线比对 + 原始请求 fuzz）
│   ├── mutator.py    # 通用字节级变异器
│   ├── request.py    # Burp 风格原始 HTTP 请求解析
│   └── payloads.py   # 内置载荷集 + 错误特征库
├── tools/
│   ├── base.py       # 外部命令安全封装（无 shell=True / 超时 / 可用性检测）
│   ├── nmap.py       # nmap 封装 + XML 解析
│   ├── sqlmap.py     # sqlmap 封装 + 输出解析
│   ├── nuclei.py     # nuclei 封装 + JSONL 解析
│   └── gobuster.py   # gobuster 封装 + 输出解析
└── pentest/
    └── orchestrator.py  # 自动化流水线
```

## 合规与边界

- 默认拒绝：无授权范围 / 未确认授权 → 不执行任何主动流量。
- 内置载荷为**探测级**（用于识别征兆），非利用 PoC。
- 不包含任何拒绝服务、规避检测、横向移动或数据窃取功能。
- 请遵守目标的授权书 / 漏洞披露政策 / 当地法律。
