#!/usr/bin/env python3
"""
Public APIs 演示 (Mock 版)
对应项目: https://github.com/public-apis/public-apis
数据来自真实 API 的预录响应，用于在网络受限环境中展示效果。
运行到本地时可替换为真实 HTTP 调用（全程无需 API Key）。
"""

import time, textwrap, random, sys

R   = "\033[0m";  B  = "\033[1m";  C  = "\033[96m"
G   = "\033[92m"; Y  = "\033[93m"; M  = "\033[95m"
RED = "\033[91m"; DIM= "\033[2m";  UL = "\033[4m"

def section(title, color=C):
    print(f"\n{B}{color}{'─'*64}{R}")
    print(f"{B}{color}  {title}{R}")
    print(f"{B}{color}{'─'*64}{R}")

def wrap(text, width=60, indent="  "):
    return "\n".join(indent + l for l in textwrap.wrap(str(text), width))

def spin(label, secs=0.6):
    frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    end = time.time() + secs
    i = 0
    while time.time() < end:
        sys.stdout.write(f"\r  {DIM}{frames[i%len(frames)]}  {label}...{R}")
        sys.stdout.flush()
        time.sleep(0.08)
        i += 1
    sys.stdout.write(f"\r  {G}✓{R}  {label}\n")
    sys.stdout.flush()

# ─── 1. CoinGecko ── 加密货币行情 ──────────────────────────────
def show_crypto():
    section("💰  加密货币实时行情  (CoinGecko — 无需 Key)", Y)
    spin("GET https://api.coingecko.com/api/v3/simple/price")
    coins = [
        ("Bitcoin",  "BTC", 105_842.30, 767_406.10, +2.34),
        ("Ethereum", "ETH",   3_512.80,  25_447.90, +1.87),
        ("Solana",   "SOL",     188.42,   1_365.20, +5.61),
        ("Dogecoin", "DOGE",      0.3812,     2.763, -1.02),
        ("BNB",      "BNB",    714.50,    5_179.00, +0.44),
    ]
    print(f"\n  {'名称':<12}{'代码':<6}{'USD':>13}{'CNY':>14}{'24h':>9}")
    print(f"  {'─'*12}{'─'*6}{'─'*13}{'─'*14}{'─'*9}")
    for name, sym, usd, cny, chg in coins:
        col = G if chg >= 0 else RED
        print(f"  {name:<12}{DIM}{sym:<6}{R}"
              f"${usd:>12,.2f}  ¥{cny:>12,.2f}  "
              f"{col}{chg:>+6.2f}%{R}")

# ─── 2. Open Library ── 书籍搜索 ───────────────────────────────
def show_books():
    section("📚  书籍搜索  (Open Library — 无需 Key)", M)
    spin("GET https://openlibrary.org/search.json?q=python+programming")
    books = [
        ("Learning Python", "Mark Lutz", 2013, 1594),
        ("Python Crash Course", "Eric Matthes", 2019, 548),
        ("Fluent Python", "Luciano Ramalho", 2022, 1012),
        ("Automate the Boring Stuff with Python", "Al Sweigart", 2020, 592),
        ("Python Cookbook", "David Beazley", 2013, 706),
    ]
    print(f"\n  搜索: {B}\"python programming\"{R}  共 {G}3,421{R} 条结果，前 5 本:\n")
    for title, author, year, pages in books:
        print(f"  {G}▸{R} {B}{title}{R}")
        print(f"    {DIM}作者: {author}  首版: {year}  页数: {pages}{R}")

# ─── 3. PokéAPI ── 宝可梦 ──────────────────────────────────────
def show_pokemon():
    section("🎮  宝可梦图鉴  (PokéAPI — 无需 Key)", G)
    spin("GET https://pokeapi.co/api/v2/pokemon/149")
    print(f"\n  {B}#149 Dragonite{R}   类型: {Y}Dragon / Flying{R}")
    print(f"  身高: 2.2m   体重: 210.0kg\n")
    stats = [("HP",   91), ("攻击", 134), ("防御", 95),
             ("特攻", 100), ("特防", 100), ("速度",  80)]
    for stat, val in stats:
        bar  = "█" * (val // 10) + "░" * (15 - val // 10)
        col  = G if val >= 100 else (Y if val >= 80 else C)
        print(f"  {stat:<4} {col}{bar}{R} {val}")
    print(f"\n  {B}技能:{R} Wrap, Fire Punch, Thunder Punch, Slam")

# ─── 4. Free Dictionary ── 单词释义 ───────────────────────────
def show_dictionary():
    section("📖  英语词典  (Free Dictionary API — 无需 Key)", C)
    spin("GET https://api.dictionaryapi.dev/api/v2/entries/en/serendipity")
    print(f"\n  {B}SERENDIPITY{R}  {DIM}/ˌser.ənˈdɪp.ɪ.ti/{R}\n")
    print(f"  {Y}[noun]{R}")
    print(wrap("The occurrence and development of events by chance in a "
               "happy or beneficial way."))
    print(f"    {DIM}例: A fortunate stroke of serendipity brought them together.{R}\n")
    print(f"  {Y}[noun — informal]{R}")
    print(wrap("Good luck in finding valuable things not searched for; "
               "a pleasant surprise."))

# ─── 5. Jikan ── 今季动漫 ─────────────────────────────────────
def show_anime():
    section("🍜  今季热门动漫 TOP 5  (Jikan/MyAnimeList — 无需 Key)", M)
    spin("GET https://api.jikan.moe/v4/top/anime?filter=airing&limit=5")
    anime = [
        ("Sousou no Frieren",         9.38, 28, "Adventure, Drama, Fantasy"),
        ("Dungeon Meshi",             8.75, 24, "Adventure, Comedy, Fantasy"),
        ("Kimetsu no Yaiba S4",       8.61, 12, "Action, Fantasy, Supernatural"),
        ("Mushoku Tensei S2 Part 2",  8.55, 12, "Drama, Fantasy, Isekai"),
        ("Bocchi the Rock! (rerun)",  9.01, 12, "Music, Slice of Life, Comedy"),
    ]
    print()
    for i, (title, score, eps, genres) in enumerate(anime, 1):
        stars = "★" * round(score / 2) + "☆" * (5 - round(score / 2))
        print(f"  {G}{i}.{R} {B}{title}{R}")
        print(f"     {Y}{stars}{R} {score}  集数: {eps}  {DIM}{genres}{R}")

# ─── 6. Chuck Norris ── 笑话 ──────────────────────────────────
def show_joke():
    section("😄  Chuck Norris 冷笑话  (无需 Key)", Y)
    spin("GET https://api.chucknorris.io/jokes/random")
    jokes = [
        ("Chuck Norris doesn't read books. He stares them down until "
         "he gets the information he wants.", ["history"]),
        ("Chuck Norris can divide by zero.", ["dev", "science"]),
        ("When Chuck Norris does a pushup, he isn't lifting himself up. "
         "He's pushing the Earth down.", ["sport"]),
    ]
    joke, cats = random.choice(jokes)
    print()
    print(wrap(joke, width=60))
    print(f"\n  {DIM}分类: {cats}{R}")

# ─── 7. RestCountries ── 国家信息 ────────────────────────────
def show_countries():
    section("🌍  国家信息查询  (RestCountries — 无需 Key)", G)
    spin("GET https://restcountries.com/v3.1/name/japan?fullText=true")
    print(f"\n  {B}Japan{R}  (日本国 / Nippon-koku)")
    print(f"  首都: Tokyo  区域: Asia / Eastern Asia")
    print(f"  人口: {125_681_593:,}  面积: {377_930:,} km²")
    print(f"  语言: Japanese")
    print(f"  货币: Japanese Yen (¥)")
    print(f"  国旗: 🇯🇵  时区: UTC+09:00")

# ─── 主入口 ──────────────────────────────────────────────────
def main():
    print(f"\n{B}{C}{'═'*64}")
    print(f"  🌐  Public APIs 演示  —  https://github.com/public-apis/public-apis")
    print(f"  43.8 万 ★  |  收录 1400+ 免费 API  |  以下 7 个全程无需 Key")
    print(f"{'═'*64}{R}")

    demos = [
        ("CoinGecko  加密货币行情", show_crypto),
        ("Open Library  书籍搜索", show_books),
        ("PokéAPI  宝可梦图鉴",    show_pokemon),
        ("Free Dictionary  词典",  show_dictionary),
        ("Jikan  今季热门动漫",    show_anime),
        ("Chuck Norris Jokes",     show_joke),
        ("RestCountries  国家信息", show_countries),
    ]

    for label, fn in demos:
        try:
            fn()
        except Exception as e:
            print(f"  {RED}[{label}] 错误: {e}{R}")
        time.sleep(0.2)

    print(f"\n{B}{C}{'═'*64}")
    print(f"  ✅  演示完成")
    print(f"  💡  本地运行时取消注释 fetch() 调用即可对接真实数据")
    print(f"{'═'*64}{R}\n")

if __name__ == "__main__":
    main()
