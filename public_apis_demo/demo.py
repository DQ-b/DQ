#!/usr/bin/env python3
"""
Public APIs 演示 - 对应项目: https://github.com/public-apis/public-apis
调用多个完全免费（无需 Key）的公开 API，实时展示结果。
"""

import urllib.request
import urllib.error
import json
import sys
import time
import textwrap
import random

# ANSI 颜色
R  = "\033[0m"
B  = "\033[1m"
C  = "\033[96m"
G  = "\033[92m"
Y  = "\033[93m"
M  = "\033[95m"
RED = "\033[91m"
DIM = "\033[2m"

def fetch(url, timeout=8):
    req = urllib.request.Request(url, headers={"User-Agent": "public-apis-demo/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())

def section(title, color=C):
    print(f"\n{B}{color}{'─'*62}{R}")
    print(f"{B}{color}  {title}{R}")
    print(f"{B}{color}{'─'*62}{R}")

def wrap(text, width=58, indent="  "):
    return "\n".join(indent + l for l in textwrap.wrap(str(text), width))

# ── 1. CoinGecko ── 加密货币实时价格 ──────────────────────────
def show_crypto():
    section("💰  加密货币实时行情  (CoinGecko — 无需 Key)", Y)
    url = ("https://api.coingecko.com/api/v3/simple/price"
           "?ids=bitcoin,ethereum,solana,dogecoin,bnb"
           "&vs_currencies=usd,cny"
           "&include_24hr_change=true")
    try:
        data = fetch(url)
        print(f"  {'名称':<12} {'USD':>12} {'CNY':>12} {'24h%':>9}")
        print(f"  {'─'*12} {'─'*12} {'─'*12} {'─'*9}")
        names = {"bitcoin":"Bitcoin","ethereum":"Ethereum",
                 "solana":"Solana","dogecoin":"Dogecoin","bnb":"BNB"}
        for coin, vals in data.items():
            usd = f"${vals['usd']:,.2f}"
            cny = f"¥{vals['cny']:,.1f}"
            chg = vals.get('usd_24h_change', 0) or 0
            chg_col = G if chg >= 0 else RED
            chg_str = f"{chg:+.2f}%"
            print(f"  {names.get(coin, coin):<12} {usd:>12} {cny:>12} "
                  f"{chg_col}{chg_str:>9}{R}")
    except Exception as e:
        print(f"  {RED}请求失败: {e}{R}")

# ── 2. Open Library ── 书籍搜索 ───────────────────────────────
def show_books():
    section("📚  书籍搜索  (Open Library — 无需 Key)", M)
    queries = ["python programming", "machine learning", "三体"]
    q = random.choice(queries)
    url = f"https://openlibrary.org/search.json?q={urllib.request.quote(q)}&limit=5"
    try:
        data = fetch(url)
        total = data.get("numFound", 0)
        print(f"  搜索关键词: {B}{q}{R}  共 {total:,} 条结果，展示前 5 本:\n")
        for doc in data.get("docs", [])[:5]:
            title = doc.get("title", "—")
            author = ", ".join(doc.get("author_name", ["未知作者"])[:2])
            year = doc.get("first_publish_year", "—")
            print(f"  {G}▸{R} {B}{title}{R}")
            print(f"    {DIM}作者: {author}  |  首次出版: {year}{R}")
    except Exception as e:
        print(f"  {RED}请求失败: {e}{R}")

# ── 3. PokéAPI ── 宝可梦图鉴 ──────────────────────────────────
def show_pokemon():
    section("🎮  宝可梦图鉴  (PokéAPI — 无需 Key)", G)
    pid = random.randint(1, 151)
    url = f"https://pokeapi.co/api/v2/pokemon/{pid}"
    try:
        data = fetch(url)
        name = data["name"].capitalize()
        hp    = next(s["base_stat"] for s in data["stats"] if s["stat"]["name"]=="hp")
        atk   = next(s["base_stat"] for s in data["stats"] if s["stat"]["name"]=="attack")
        defn  = next(s["base_stat"] for s in data["stats"] if s["stat"]["name"]=="defense")
        spd   = next(s["base_stat"] for s in data["stats"] if s["stat"]["name"]=="speed")
        types = " / ".join(t["type"]["name"].capitalize() for t in data["types"])
        moves = [m["move"]["name"] for m in data["moves"][:4]]
        height = data["height"] / 10
        weight = data["weight"] / 10
        print(f"  {B}#{pid:03d} {name}{R}   类型: {Y}{types}{R}")
        print(f"  身高: {height}m   体重: {weight}kg")
        print(f"\n  {B}基础属性:{R}")
        bars = {"HP":hp, "攻击":atk, "防御":defn, "速度":spd}
        for stat, val in bars.items():
            bar = "█" * (val // 10) + "░" * (15 - val // 10)
            print(f"  {stat:<4} {C}{bar}{R} {val}")
        print(f"\n  {B}技能:{R} {', '.join(m.replace('-',' ').title() for m in moves)}")
    except Exception as e:
        print(f"  {RED}请求失败: {e}{R}")

# ── 4. Free Dictionary ── 单词释义 ────────────────────────────
def show_dictionary():
    section("📖  英语词典  (Free Dictionary API — 无需 Key)", C)
    words = ["serendipity", "ephemeral", "ubiquitous", "resilience"]
    word = random.choice(words)
    url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
    try:
        data = fetch(url)
        entry = data[0]
        phonetic = entry.get("phonetic", "")
        print(f"  {B}{word.upper()}{R}  {DIM}{phonetic}{R}\n")
        for meaning in entry.get("meanings", [])[:3]:
            pos = meaning["partOfSpeech"]
            print(f"  {Y}[{pos}]{R}")
            for defn in meaning.get("definitions", [])[:2]:
                print(wrap(defn["definition"]))
                if defn.get("example"):
                    print(f"    {DIM}例: {defn['example']}{R}")
            print()
    except Exception as e:
        print(f"  {RED}请求失败: {e}{R}")

# ── 5. Jikan ── 动漫信息 ──────────────────────────────────────
def show_anime():
    section("🍜  今季热门动漫  (Jikan/MyAnimeList — 无需 Key)", M)
    url = "https://api.jikan.moe/v4/top/anime?limit=5&filter=airing"
    try:
        data = fetch(url)
        for i, anime in enumerate(data.get("data", [])[:5], 1):
            title = anime.get("title", "—")
            score = anime.get("score") or "N/A"
            eps   = anime.get("episodes") or "?"
            genres = ", ".join(g["name"] for g in anime.get("genres", [])[:3])
            print(f"  {G}{i}.{R} {B}{title}{R}")
            print(f"     评分: {Y}{score}{R}  集数: {eps}  {DIM}{genres}{R}")
    except Exception as e:
        print(f"  {RED}请求失败: {e}{R}")

# ── 6. Chuck Norris ── 冷知识/笑话 ───────────────────────────
def show_joke():
    section("😄  Chuck Norris 冷笑话  (无需 Key)", Y)
    url = "https://api.chucknorris.io/jokes/random"
    try:
        data = fetch(url)
        print(wrap(data["value"], width=58))
        print(f"\n  {DIM}分类: {data.get('categories') or ['通用']}{R}")
    except Exception as e:
        print(f"  {RED}请求失败: {e}{R}")

# ── 7. RestCountries ── 国家信息 ─────────────────────────────
def show_countries():
    section("🌍  国家信息查询  (RestCountries — 无需 Key)", G)
    countries = ["china", "japan", "france", "brazil", "nigeria"]
    name = random.choice(countries)
    url = f"https://restcountries.com/v3.1/name/{name}?fullText=true"
    try:
        data = fetch(url)
        c = data[0]
        cname    = c["name"]["common"]
        official = c["name"]["official"]
        capital  = c.get("capital", ["—"])[0]
        pop      = c.get("population", 0)
        area     = c.get("area", 0)
        region   = c.get("region", "—")
        langs    = ", ".join(c.get("languages", {}).values())
        currencies = ", ".join(
            f"{v['name']}({v.get('symbol','')})"
            for v in c.get("currencies", {}).values()
        )
        print(f"  {B}{cname}{R}  ({official})")
        print(f"  首都: {capital}  区域: {region}")
        print(f"  人口: {pop:,}  面积: {area:,.0f} km²")
        print(f"  语言: {langs}")
        print(f"  货币: {currencies}")
    except Exception as e:
        print(f"  {RED}请求失败: {e}{R}")

# ── 主入口 ─────────────────────────────────────────────────────
def main():
    print(f"\n{B}{C}{'═'*62}")
    print(f"  🌐  Public APIs 演示")
    print(f"  项目: https://github.com/public-apis/public-apis")
    print(f"  共 43.8 万 ★  |  全程无需 API Key")
    print(f"{'═'*62}{R}")

    demos = [
        ("加密货币行情",  show_crypto),
        ("书籍搜索",      show_books),
        ("宝可梦图鉴",    show_pokemon),
        ("英语词典",      show_dictionary),
        ("热门动漫",      show_anime),
        ("Chuck Norris",  show_joke),
        ("国家信息",      show_countries),
    ]

    for label, fn in demos:
        try:
            fn()
        except Exception as e:
            print(f"  {RED}[{label}] 意外错误: {e}{R}")
        time.sleep(0.4)   # 礼貌性限速

    print(f"\n{B}{C}{'═'*62}")
    print(f"  ✅  演示完成  — 以上全部来自免费公开 API")
    print(f"{'═'*62}{R}\n")

if __name__ == "__main__":
    main()
