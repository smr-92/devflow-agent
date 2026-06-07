"""Score multiple MRs in sequence and populate the Firestore leaderboard."""
import asyncio
import sys
import os
from dotenv import load_dotenv
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

# reuse the agent defined in agent.py
from agent import agent

load_dotenv()

PROJECT_ID = "smr_92/devpost_sample_project"


async def score_mr(runner: Runner, session_id: str, mr_iid: int) -> str:
    prompt = f"Score merge request #{mr_iid} in project {PROJECT_ID}"
    result = ""
    async for event in runner.run_async(
        user_id="dev_1",
        session_id=session_id,
        new_message=types.Content(
            role="user",
            parts=[types.Part(text=prompt)]
        )
    ):
        if hasattr(event, "content") and event.content:
            for part in event.content.parts:
                if hasattr(part, "text") and part.text:
                    result += part.text
    return result.strip()


async def main():
    # default: score MRs 2-10; pass args to override e.g. `python score_batch.py 2 15`
    start = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    end   = int(sys.argv[2]) if len(sys.argv) > 2 else 10

    session_service = InMemorySessionService()
    runner = Runner(agent=agent, app_name="devflow", session_service=session_service)

    for mr_iid in range(start, end + 1):
        session = await session_service.create_session(app_name="devflow", user_id="dev_1")
        print(f"\n── MR #{mr_iid} ──────────────────────────────────")
        for attempt in range(3):
            try:
                result = await score_mr(runner, session.id, mr_iid)
                print(result)
                break
            except Exception as e:
                if attempt < 2:
                    wait = 15 * (attempt + 1)
                    print(f"  ⚠ Error (attempt {attempt+1}/3): {e!s:.80}... retrying in {wait}s")
                    await asyncio.sleep(wait)
                else:
                    print(f"  ✗ Failed after 3 attempts: {e!s:.120}")
        await asyncio.sleep(5)

    print("\n\nAll done. Fetching leaderboard...")
    session = await session_service.create_session(app_name="devflow", user_id="dev_1")
    async for event in runner.run_async(
        user_id="dev_1",
        session_id=session.id,
        new_message=types.Content(
            role="user",
            parts=[types.Part(text="Show the current leaderboard")]
        )
    ):
        if hasattr(event, "content") and event.content and event.content.parts:
            for part in event.content.parts:
                if hasattr(part, "text") and part.text:
                    print(part.text)


if __name__ == "__main__":
    asyncio.run(main())
