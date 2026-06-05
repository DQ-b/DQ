import asyncio
import os
import glob
from dotenv import load_dotenv
from browser_use import Agent
from browser_use.llm.deepseek.chat import ChatDeepSeek
from browser_use.browser.profile import BrowserProfile
from browser_use.browser.session import BrowserSession

load_dotenv()

# 自动找到 Windows 上 playwright 安装的 Chromium
chromium_candidates = glob.glob(
    os.path.expanduser(r"~\AppData\Local\ms-playwright\chromium-*\chrome-win\chrome.exe")
)
chromium_path = chromium_candidates[0] if chromium_candidates else None
print(f"使用 Chromium: {chromium_path}")

llm = ChatDeepSeek(
    model="deepseek-chat",
    api_key=os.getenv("DEEPSEEK_API_KEY"),
)

browser_profile = BrowserProfile(
    executable_path=chromium_path,
    headless=False,
)

async def main():
    browser_session = BrowserSession(browser_profile=browser_profile)
    agent = Agent(
        task=(
            "打开 https://www.xiaohongshu.com ，"
            "如果出现登录弹窗就关闭它，"
            "然后在搜索框输入 'AI最新知识' 并搜索，"
            "把前 5 条笔记的标题和作者列出来。"
        ),
        llm=llm,
        browser_session=browser_session,
    )
    result = await agent.run()
    print("\n=== 任务结果 ===")
    print(result)

if __name__ == "__main__":
    asyncio.run(main())
