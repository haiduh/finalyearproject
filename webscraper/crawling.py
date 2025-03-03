import asyncio
import json
from crawl4ai import *

user_input = input("Enter a website: ")

async def main():
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(
            url=user_input,
        )
        print(result.markdown)

if __name__ == "__main__":
    asyncio.run(main())