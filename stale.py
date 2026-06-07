"""Scan a GitLab project for stale MRs and post reminder comments on each."""
import asyncio
import sys
import os
from datetime import datetime, timezone
from dotenv import load_dotenv
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from agent import agent

load_dotenv()

PROJECT_ID  = os.getenv("DEVFLOW_PROJECT", "smr_92/devpost_sample_project")
THRESHOLD   = int(os.getenv("STALE_DAYS", "2"))


async def main():
    project_id = sys.argv[1] if len(sys.argv) > 1 else PROJECT_ID
    threshold  = int(sys.argv[2]) if len(sys.argv) > 2 else THRESHOLD
    today      = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    session_service = InMemorySessionService()
    session = await session_service.create_session(app_name="devflow", user_id="stale_scanner")
    runner  = Runner(agent=agent, app_name="devflow", session_service=session_service)

    prompt = (
        f"Today is {today}. "
        f"Check for stale MRs in project {project_id} "
        f"(stale = no activity for {threshold}+ days). "
        f"Post a stale alert comment on each one."
    )

    print(f"Scanning {project_id} for MRs inactive for {threshold}+ days...\n")

    async for event in runner.run_async(
        user_id="stale_scanner",
        session_id=session.id,
        new_message=types.Content(role="user", parts=[types.Part(text=prompt)])
    ):
        if hasattr(event, "content") and event.content and event.content.parts:
            for part in event.content.parts:
                if hasattr(part, "text") and part.text:
                    print(part.text)


if __name__ == "__main__":
    asyncio.run(main())
