import asyncio, os
from dotenv import load_dotenv
from browser_use import Agent
from browser_use.llm.deepseek.chat import ChatDeepSeek
from browser_use.browser.profile import BrowserProfile
from browser_use.browser.session import BrowserSession

load_dotenv()
llm = ChatDeepSeek(model='deepseek-chat', api_key=os.getenv('DEEPSEEK_API_KEY'))
browser_profile = BrowserProfile(headless=False)

async def main():
    agent = Agent(
        task=(
            "打开 http://47.107.106.112:8080 ，"
            "在手机号输入框输入 13800138000，"
            "在密码输入框输入 123456，"
            "点击登录按钮，"
            "告诉我登录后页面显示的内容。"
        ),
        llm=llm,
        browser_session=BrowserSession(browser_profile=browser_profile)
    )
    print(await agent.run())

asyncio.run(main())
