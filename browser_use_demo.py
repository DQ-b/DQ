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
    executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
    headless=True,
    args=[
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--ignore-certificate-errors",
    ],
)

async def main():
    browser_session = BrowserSession(browser_profile=browser_profile)
    agent = Agent(
        task="打开 https://www.baidu.com 并搜索'今日天气'，告诉我搜索结果页面的标题",
        llm=llm,
        browser_session=browser_session,
    )
    result = await agent.run()
    print("\n✅ 任务结果:", result)

if __name__ == "__main__":
    asyncio.run(main())
