import asyncio, os
from dotenv import load_dotenv
from browser_use import Agent
from browser_use.llm.deepseek.chat import ChatDeepSeek
from browser_use.browser.profile import BrowserProfile
from browser_use.browser.session import BrowserSession

load_dotenv()
llm = ChatDeepSeek(model='deepseek-chat', api_key=os.getenv('DEEPSEEK_API_KEY'))

USERS = [
    {"phone": "13900000001", "password": "Test1234"},
    {"phone": "13900000002", "password": "Test1234"},
    {"phone": "13900000003", "password": "Test1234"},
]

async def register_user(phone, password):
    browser_profile = BrowserProfile(headless=False)
    browser_session = BrowserSession(browser_profile=browser_profile)
    agent = Agent(
        task=(
            f"打开 http://47.107.106.112:8080 ，"
            f"点击'没有账号？立即注册'链接，"
            f"在注册页面填写手机号 {phone}，密码 {password}，"
            f"完成注册，告诉我注册过程中每一步显示的内容和最终结果。"
        ),
        llm=llm,
        browser_session=browser_session,
    )
    result = await agent.run()
    return result

async def main():
    results = []
    for i, user in enumerate(USERS, 1):
        print(f"\n{'='*50}")
        print(f"正在注册用户 {i}: {user['phone']}")
        print('='*50)
        result = await register_user(user['phone'], user['password'])
        results.append({
            "user": user['phone'],
            "result": result
        })
        print(f"\n用户 {user['phone']} 注册结果：\n{result}")
        await asyncio.sleep(2)

    print("\n\n" + "="*50)
    print("所有用户注册完成，汇总报告：")
    print("="*50)
    for r in results:
        print(f"\n📱 {r['user']}：{r['result']}")

if __name__ == "__main__":
    asyncio.run(main())
