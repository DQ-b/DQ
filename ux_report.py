import asyncio, os
from dotenv import load_dotenv
from browser_use import Agent
from browser_use.llm.deepseek.chat import ChatDeepSeek
from browser_use.browser.profile import BrowserProfile
from browser_use.browser.session import BrowserSession

load_dotenv()
llm = ChatDeepSeek(model="deepseek-chat", api_key=os.getenv("DEEPSEEK_API_KEY"))

ROLES = [
    {
        "name": "新手散户 - 小王",
        "desc": "28岁上班族，刚开始炒股3个月，不懂技术分析，想找简单的买卖信号",
        "task": (
            "你是一个28岁的上班族新手散户，刚开始炒股3个月，不懂技术分析。"
            "打开 http://47.107.106.112:8080 ，用账号13800138000密码123456登录，"
            "以新手的视角浏览网站，尝试找到今天应该买什么股票的信息，"
            "记录你在每个页面看到了什么、哪些地方看不懂、哪些地方觉得有用，"
            "最后给出你作为新手的真实感受和评价。"
        )
    },
    {
        "name": "资深股民 - 老李",
        "desc": "50岁，炒股20年，关注技术面和基本面，每天盯盘，追求稳健收益",
        "task": (
            "你是一个50岁的资深股民，炒股20年，关注技术面和基本面，每天盯盘。"
            "打开 http://47.107.106.112:8080 ，用账号13800138000密码123456登录，"
            "重点查看大盘指数、策略信号、热门板块、个股榜单，"
            "对比你20年的经验评估这个网站的数据质量和策略可靠性，"
            "指出哪些功能对你有价值，哪些不足，给出专业评价。"
        )
    },
    {
        "name": "量化研究员 - 陈博士",
        "desc": "35岁，金融学博士，做量化投资，关注策略逻辑和数据准确性",
        "task": (
            "你是一个35岁的金融学博士，专注量化投资研究。"
            "打开 http://47.107.106.112:8080 ，用账号13800138000密码123456登录，"
            "重点研究策略回测功能、AI设置、策略信号的逻辑，"
            "评估策略的科学性、数据的准确性、回测的可信度，"
            "从量化研究角度给出专业的技术评价和改进建议。"
        )
    },
    {
        "name": "职场白领 - 小林",
        "desc": "32岁女性，工作繁忙，每天只有10分钟看股票，希望快速获取核心信息",
        "task": (
            "你是一个32岁的职场女性，工作繁忙，每天只有10分钟看股票。"
            "打开 http://47.107.106.112:8080 ，用账号13800138000密码123456登录，"
            "模拟只有10分钟的情况下快速浏览，看能否在最短时间内获取今日核心投资信息，"
            "评估网站信息获取效率、界面是否直观、对忙碌用户是否友好，"
            "给出你作为时间有限用户的真实使用体验。"
        )
    },
]

async def run_role(role):
    print(f"\n{'='*60}")
    print(f"角色：{role['name']}")
    print(f"背景：{role['desc']}")
    print('='*60)
    agent = Agent(
        task=role["task"],
        llm=llm,
        browser_session=BrowserSession(browser_profile=BrowserProfile(headless=False))
    )
    result = await agent.run()
    return result

async def main():
    reports = []
    for role in ROLES:
        result = await run_role(role)
        reports.append({"role": role["name"], "report": result})
        print(f"\n📋 {role['name']} 体验报告：\n{result}")
        await asyncio.sleep(3)

    print("\n\n" + "="*60)
    print("所有角色体验完成！")
    print("="*60)
    for r in reports:
        print(f"\n👤 {r['role']}")
        print(r["report"])
        print("-"*60)

asyncio.run(main())
