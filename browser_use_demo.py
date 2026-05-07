"""
Browser Use + Claude — minimal local demo.

Watch an AI agent open a browser, navigate to Hacker News,
and report the top 3 story titles.

-----------------------------------------------------------------
SETUP (one time)
-----------------------------------------------------------------

    # Use Python 3.11 or newer
    python --version

    # Create and activate a virtual environment
    python -m venv .venv
    source .venv/bin/activate            # macOS / Linux
    .venv\\Scripts\\activate              # Windows

    # Install dependencies
    pip install "browser-use>=0.12" anthropic playwright
    playwright install chromium

-----------------------------------------------------------------
RUN
-----------------------------------------------------------------

    export ANTHROPIC_API_KEY=sk-ant-...   # macOS / Linux
    set    ANTHROPIC_API_KEY=sk-ant-...   # Windows (cmd)
    $env:ANTHROPIC_API_KEY="sk-ant-..."   # Windows (PowerShell)

    python browser_use_demo.py
"""

import asyncio
import os
import sys

from browser_use import Agent, Browser, ChatAnthropic


async def main() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit(
            "ANTHROPIC_API_KEY is not set. "
            "See the SETUP section at the top of this file."
        )

    # headless=False is intentional to watch the browser navigate.
    # Flip to True if you just want the answer.
    browser = Browser(
        headless=False,
        allowed_domains=["news.ycombinator.com"],
    )

    agent = Agent(
        task=(
            "Go to https://news.ycombinator.com and return the titles "
            "of the top 3 stories as a numbered list."
        ),
        # select a model of your choice
        # for tasks like this, open source might make sense?
        llm=ChatAnthropic(model="claude-sonnet-4-6"),
        browser=browser,
    )

    result = await agent.run(max_steps=10)

    print("\n--- Final answer ---")
    print(result.final_result() or "(no final answer, see log above)")


if __name__ == "__main__":
    asyncio.run(main())
