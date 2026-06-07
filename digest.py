"""Generate and print a daily team digest for a GitLab project."""
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

PROJECT_ID = os.getenv("DEVFLOW_PROJECT", "smr_92/devpost_sample_project")


async def main():
    project_id = sys.argv[1] if len(sys.argv) > 1 else PROJECT_ID
    today      = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    session_service = InMemorySessionService()
    session = await session_service.create_session(app_name="devflow", user_id="digest")
    runner  = Runner(agent=agent, app_name="devflow", session_service=session_service)

    prompt = (
        f"Today is {today}. "
        f"Generate a full daily digest for project {project_id}. "
        f"Include: all open MRs with days since update, stale MRs (2+ days inactive), "
        f"open issues count, current leaderboard top 5, and a team health summary."
    )

    print(f"DevFlow Daily Digest — {today}\n{'='*50}\n")

    async for event in runner.run_async(
        user_id="digest",
        session_id=session.id,
        new_message=types.Content(role="user", parts=[types.Part(text=prompt)])
    ):
        if hasattr(event, "content") and event.content and event.content.parts:
            for part in event.content.parts:
                if hasattr(part, "text") and part.text:
                    print(part.text)


if __name__ == "__main__":
    asyncio.run(main())
