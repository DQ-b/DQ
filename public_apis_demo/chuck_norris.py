#!/usr/bin/env python3
"""
Chuck Norris Jokes API 完整接入示例
API 文档: https://api.chucknorris.io
无需注册 / 无需 API Key / 完全免费
"""

import urllib.request
import urllib.parse
import json
import sys
import time
import textwrap

# ── ANSI 颜色 ────────────────────────────────────────────────
R   = "\033[0m";   B  = "\033[1m";   C  = "\033[96m"
G   = "\033[92m";  Y  = "\033[93m";  M  = "\033[95m"
RED = "\033[91m";  DIM= "\033[2m";   UL = "\033[4m"

BASE = "https://api.chucknorris.io"

# ── HTTP 工具 ─────────────────────────────────────────────────
def get(path, params=None):
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url, headers={"User-Agent": "chuck-norris-demo/1.0",
                      "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=8) as r:
        return json.loads(r.read().decode())

# ── API 封装 ──────────────────────────────────────────────────

def random_joke(category=None):
    """随机获取一条笑话，可指定分类"""
    params = {"category": category} if category else None
    return get("/jokes/random", params)

def get_categories():
    """获取所有笑话分类"""
    return get("/jokes/categories")

def search_jokes(query):
    """按关键词搜索笑话"""
    return get("/jokes/search", {"query": query})

def joke_by_id(joke_id):
    """按 ID 获取指定笑话"""
    return get(f"/jokes/{joke_id}")

# ── 格式化输出 ────────────────────────────────────────────────

def print_joke(joke, index=None):
    prefix = f"{Y}#{index}{R} " if index else ""
    text = textwrap.fill(joke["value"], width=62,
                         initial_indent="  ", subsequent_indent="  ")
    cats = joke.get("categories") or ["general"]
    print(f"\n{prefix}{text}")
    print(f"  {DIM}分类: {', '.join(cats)}  |  ID: {joke['id'][:8]}...{R}")

def header(title):
    print(f"\n{B}{C}{'─'*64}{R}")
    print(f"{B}{C}  {title}{R}")
    print(f"{B}{C}{'─'*64}{R}")

# ── 演示所有功能 ──────────────────────────────────────────────

def demo():
    print(f"\n{B}{C}{'═'*64}")
    print(f"  😄  Chuck Norris Jokes API  接入演示")
    print(f"  https://api.chucknorris.io  |  无需 Key  |  永久免费")
    print(f"{'═'*64}{R}")

    # 1. 获取所有分类
    header("① 获取所有笑话分类  GET /jokes/categories")
    categories = get_categories()
    cols = 4
    for i in range(0, len(categories), cols):
        row = categories[i:i+cols]
        print("  " + "   ".join(f"{G}{c:<16}{R}" for c in row))
    print(f"\n  共 {Y}{len(categories)}{R} 个分类")

    time.sleep(0.3)

    # 2. 随机笑话（无分类）
    header("② 随机笑话  GET /jokes/random")
    j = random_joke()
    print_joke(j)

    time.sleep(0.3)

    # 3. 指定分类随机笑话
    header("③ 指定分类笑话  GET /jokes/random?category=dev")
    for cat in ["dev", "science", "sport"]:
        j = random_joke(category=cat)
        print(f"\n  {M}[{cat}]{R}")
        text = textwrap.fill(j["value"], width=60,
                             initial_indent="  ", subsequent_indent="  ")
        print(text)
        time.sleep(0.2)

    # 4. 关键词搜索
    header("④ 关键词搜索  GET /jokes/search?query=internet")
    results = search_jokes("internet")
    total = results["total"]
    print(f"  关键词: {B}\"internet\"{R}  共找到 {Y}{total}{R} 条\n")
    for i, j in enumerate(results["result"][:3], 1):
        print_joke(j, index=i)
        time.sleep(0.1)

    # 5. 按 ID 查询
    header("⑤ 按 ID 查询  GET /jokes/{id}")
    # 先拿一个笑话的完整 ID
    sample = random_joke()
    jid = sample["id"]
    print(f"  ID: {DIM}{jid}{R}")
    j = joke_by_id(jid)
    print_joke(j)

    # 结尾
    print(f"\n{B}{C}{'═'*64}")
    print(f"  ✅  5 个接口全部调通  —  以上均为真实 API 返回数据")
    print(f"\n  {DIM}接口速查:{R}")
    endpoints = [
        ("GET /jokes/categories",         "所有分类列表"),
        ("GET /jokes/random",             "随机一条"),
        ("GET /jokes/random?category=X",  "指定分类随机"),
        ("GET /jokes/search?query=X",     "关键词搜索"),
        ("GET /jokes/{id}",               "按 ID 精确查询"),
    ]
    for ep, desc in endpoints:
        print(f"  {G}{ep:<40}{R} {DIM}{desc}{R}")
    print(f"{B}{C}{'═'*64}{R}\n")


# ── 交互式模式 ────────────────────────────────────────────────

def interactive():
    categories = get_categories()

    while True:
        print(f"\n{B}选择操作:{R}")
        print(f"  {Y}1{R} 随机笑话")
        print(f"  {Y}2{R} 按分类获取")
        print(f"  {Y}3{R} 关键词搜索")
        print(f"  {Y}q{R} 退出")
        choice = input(f"\n{G}>{R} ").strip().lower()

        if choice == "q":
            print("再见！")
            break
        elif choice == "1":
            print_joke(random_joke())
        elif choice == "2":
            print(f"\n可用分类: {', '.join(categories)}")
            cat = input(f"{G}输入分类>{R} ").strip()
            if cat in categories:
                print_joke(random_joke(category=cat))
            else:
                print(f"{RED}分类不存在{R}")
        elif choice == "3":
            q = input(f"{G}关键词>{R} ").strip()
            if q:
                res = search_jokes(q)
                print(f"\n  共 {res['total']} 条结果:")
                for i, j in enumerate(res["result"][:5], 1):
                    print_joke(j, index=i)


if __name__ == "__main__":
    if "--interactive" in sys.argv or "-i" in sys.argv:
        interactive()
    else:
        demo()
