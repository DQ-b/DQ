import asyncio
import os
from dotenv import load_dotenv
from browser_use import Agent
from browser_use.llm.deepseek.chat import ChatDeepSeek
from browser_use.browser.profile import BrowserProfile
from browser_use.browser.session import BrowserSession

load_dotenv()

llm = ChatDeepSeek(
    model="deepseek-chat",
    api_key=os.getenv("DEEPSEEK_API_KEY"),
)

browser_profile = BrowserProfile(
    headless=False,
)

async def main():
    browser_session = BrowserSession(browser_profile=browser_profile)
    agent = Agent(
        task="打开 http://47.107.106.112:8080 ，告诉我页面上显示的内容。",
        llm=llm,
        browser_session=browser_session,
    )
    result = await agent.run()
    print("\n=== 任务结果 ===")
    print(result)

if __name__ == "__main__":
    asyncio.run(main())
