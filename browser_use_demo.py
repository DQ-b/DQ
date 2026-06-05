import asyncio
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from browser_use import Agent

load_dotenv()

import os

llm = ChatOpenAI(
    model="deepseek-chat",
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com/v1",
)

async def main():
    agent = Agent(
        task="打开 https://www.baidu.com 并搜索'今日天气'",
        llm=llm,
    )
    result = await agent.run()
    print(result)

if __name__ == "__main__":
    asyncio.run(main())
