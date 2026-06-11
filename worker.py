"""
Standalone agent worker — called as a subprocess by api.py.
Usage: python worker.py "<prompt>"
Runs in its own process so MCP subprocess starts cleanly.
"""
import asyncio
import sys
import os
from dotenv import load_dotenv
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from agent import agent

load_dotenv()


async def main(prompt: str) -> None:
    session_service = InMemorySessionService()
    session = await session_service.create_session(app_name="devflow", user_id="worker")
    runner = Runner(agent=agent, app_name="devflow", session_service=session_service)

    async for event in runner.run_async(
        user_id="worker",
        session_id=session.id,
        new_message=types.Content(role="user", parts=[types.Part(text=prompt)])
    ):
        if hasattr(event, "content") and event.content and event.content.parts:
            for part in event.content.parts:
                if hasattr(part, "text") and part.text:
                    print(part.text, flush=True)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python worker.py '<prompt>'")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
