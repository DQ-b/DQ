import asyncio, os
from dotenv import load_dotenv
from browser_use import Agent
from browser_use.llm.deepseek.chat import ChatDeepSeek
from browser_use.browser.profile import BrowserProfile
from browser_use.browser.session import BrowserSession

load_dotenv()
llm = ChatDeepSeek(model="deepseek-chat", api_key=os.getenv("DEEPSEEK_API_KEY"), max_tokens=4096)

ROLES = [
    {
        "name": "新手散户 - 小王",
        "task": "打开 http://47.107.106.112:8080 用账号13800138000密码123456登录，以炒股新手身份浏览首页，找到今日买股建议，用3句话说出新手感受。"
    },
    {
        "name": "资深股民 - 老李",
        "task": "打开 http://47.107.106.112:8080 用账号13800138000密码123456登录，以20年老股民身份查看大盘和策略信号，用3句话给出专业评价。"
    },
    {
        "name": "量化研究员 - 陈博士",
        "task": "打开 http://47.107.106.112:8080 用账号13800138000密码123456登录，以量化研究员身份查看策略回测和AI设置功能，用3句话评价策略科学性。"
    },
    {
        "name": "职场白领 - 小林",
        "task": "打开 http://47.107.106.112:8080 用账号13800138000密码123456登录，以时间紧张的上班族身份快速浏览首页，用3句话说出10分钟内能获取哪些核心信息。"
    },
]

async def run_role(role):
    print("\n" + "="*50)
    print("角色：" + role["name"])
    print("="*50)
    agent = Agent(
        task=role["task"],
        llm=llm,
        browser_session=BrowserSession(browser_profile=BrowserProfile(headless=False)),
        max_failures=3,
    )
    result = await agent.run()
    return result

async def main():
    reports = []
    for role in ROLES:
        result = await run_role(role)
        reports.append({"role": role["name"], "report": result})
        print("\n报告：" + role["name"])
        print(str(result))
        await asyncio.sleep(2)

    print("\n" + "="*50)
    print("所有角色体验完成！")
    for r in reports:
        print("\n" + r["role"] + "：")
        print(str(r["report"]))

asyncio.run(main())
