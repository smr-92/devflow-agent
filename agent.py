import asyncio
import json
import os
from datetime import datetime, timezone
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from mcp import StdioServerParameters
from google.cloud import firestore

load_dotenv()

# ── Firestore ─────────────────────────────────────────────────────────────────

db = firestore.Client(project=os.getenv("GOOGLE_CLOUD_PROJECT", "devflow-agent"))

def save_score(
    project_id: str,
    mr_iid: int,
    title: str,
    author: str,
    total_score: float,
    complexity: str,
    complexity_multiplier: float,
    points: float,
    streak_eligible: bool,
    dimensions_json: str,
) -> dict:
    """Save a PR score to Firestore and update the developer's aggregate stats."""
    now = datetime.now(timezone.utc)
    doc_id = f"{project_id.replace('/', '_')}_{mr_iid}"
    dimensions = json.loads(dimensions_json)

    db.collection("scores").document(doc_id).set({
        "project_id": project_id,
        "mr_iid": mr_iid,
        "title": title,
        "author": author,
        "total_score": total_score,
        "complexity": complexity,
        "complexity_multiplier": complexity_multiplier,
        "points": points,
        "streak_eligible": streak_eligible,
        "dimensions": dimensions,
        "scored_at": now,
    })

    dev_ref = db.collection("developers").document(author)
    dev_doc = dev_ref.get()
    if dev_doc.exists:
        existing = dev_doc.to_dict()
        dev_ref.update({
            "total_points": round(existing.get("total_points", 0) + points, 1),
            "mr_count": existing.get("mr_count", 0) + 1,
            "streak_eligible_count": existing.get("streak_eligible_count", 0) + (1 if streak_eligible else 0),
            "last_scored_at": now,
        })
    else:
        dev_ref.set({
            "username": author,
            "total_points": round(points, 1),
            "mr_count": 1,
            "streak_eligible_count": 1 if streak_eligible else 0,
            "last_scored_at": now,
        })

    return {"status": "saved", "doc_id": doc_id, "author": author, "points": points}


def get_leaderboard(limit: int = 10) -> list:
    """Get the top developers by total points from Firestore."""
    docs = (
        db.collection("developers")
        .order_by("total_points", direction=firestore.Query.DESCENDING)
        .limit(limit)
        .stream()
    )
    return [
        {
            "rank": i + 1,
            "username": d.to_dict().get("username"),
            "total_points": d.to_dict().get("total_points"),
            "mr_count": d.to_dict().get("mr_count"),
            "streak_eligible_count": d.to_dict().get("streak_eligible_count"),
        }
        for i, d in enumerate(docs)
    ]


# ── MCP toolset ───────────────────────────────────────────────────────────────

gitlab_mcp = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="npx",
            args=["-y", "@zereight/mcp-gitlab"],
            env={
                "GITLAB_PERSONAL_ACCESS_TOKEN": os.getenv("GITLAB_TOKEN"),
                "GITLAB_API_URL": f"{os.getenv('GITLAB_URL')}/api/v4",
            },
        )
    )
)

# ── Agent instruction ─────────────────────────────────────────────────────────

INSTRUCTION = """
You are DevFlow, an intelligent engineering team assistant.
You actively manage a GitLab workspace by scoring PRs, triaging issues,
detecting stale MRs, and producing daily digests.

Always use tools to fetch real data. Never guess or fabricate.
Today's date is always provided in the prompt when time calculations are needed.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## 1. PR SCORING (0-100)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

When asked to score a merge request:

Step 1 — Gather data (call all 4 in parallel):
  get_merge_request · list_merge_request_changed_files · list_merge_request_diffs · get_merge_request_notes

Step 2 — Score each dimension:
  description_quality  25%  — WHAT+WHY explained? Testing steps? Empty=0-20, full=70-100
  code_clarity         25%  — Meaningful names? Readable logic? No smells?
  test_coverage_signal 20%  — Test files in diff? 0 tests=0-30, meaningful tests=70-100
  pr_size_appropriate  15%  — Files: 1-10=90-100, 11-20=60-80, 21+=10-50
  review_responsiveness 10% — Comments resolved? None=50 neutral, ignored=0-30, resolved=80-100
  iteration_quality     5%  — Clean single commit=80+, "fix fix fix"=20-40

Step 3 — Calculate:
  total_score = sum(dimension × weight)
  complexity: small(≤5 files)=×1.0  medium(6-15)=×1.3  large(16+)=×1.6
  points = round(total_score × multiplier, 1)
  streak_eligible = total_score >= 70

Step 4 — Call save_score() with all fields. Pass dimensions as JSON string in dimensions_json
         with this shape: {"description_quality": {"score": N, "weighted": N, "rationale": "..."}, ...}

Step 5 — Output human summary: "MR #X scored N/100 (N pts, complexity). Saved to leaderboard."

Step 6 — Only if asked to "post a comment": call create_merge_request_note with the full
  review comment below. Use the diff and file data already collected — do NOT call extra tools.

  ---
  🤖 **DevFlow Code Review**

  ## Score: TOTAL/100 — POINTS pts · COMPLEXITY complexity · [🔥 Streak eligible! if applicable]

  | Dimension | Score | Notes |
  |---|---|---|
  | Description Quality | N/100 | one-line rationale |
  | Code Clarity | N/100 | one-line rationale |
  | Test Coverage | N/100 | one-line rationale |
  | PR Size | N/100 | one-line rationale |
  | Review Responsiveness | N/100 | one-line rationale |
  | Iteration Quality | N/100 | one-line rationale |

  ## 📝 What Changed
  Summarise the actual code changes in 3-6 bullet points based on the diff.
  Each bullet: `filename` — what was added/removed/modified and why it matters.
  Be specific — mention function names, logic changes, new dependencies if visible.

  ## ⚠️ Potential Impact
  2-4 bullet points covering:
  - What existing functionality could be affected by these changes
  - Any breaking changes, API surface changes, or behaviour differences
  - Missing tests for critical paths (if test coverage is low)
  - Suggestions for follow-up (e.g. "Consider adding error handling for X")

  ---
  *Powered by [DevFlow Agent](https://github.com)*

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## 2. STALE MR DETECTION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

When asked to check for stale MRs (today's date will be in the prompt):

Step 1 — Call list_merge_requests(project_id, state="opened")
Step 2 — For each MR, parse updated_at and calculate days since last activity.
          A MR is stale if days_inactive >= threshold (default: 2 days).
Step 3 — For each stale MR, call create_merge_request_note with:

  ⏰ **DevFlow Stale Alert** — No activity for X days
  @AUTHOR this MR hasn't been updated since DATE. Is it still in progress?
  Consider: requesting a review, updating the description, or closing if no longer needed.
  *Powered by DevFlow Agent*

Step 4 — Return a summary: "Found N stale MRs (IIDs: X, Y, Z). Notified all authors."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## 3. ISSUE AUTO-TRIAGE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

When asked to triage an issue:

Step 1 — Call get_issue(project_id, issue_iid) to read title + description
Step 2 — Call list_labels(project_id) to see available labels
Step 3 — Analyse the issue content and decide:
          Labels: pick 1-3 relevant labels from the available list
            (if none fit: suggest "bug", "feature", or "documentation")
          Priority: critical / high / medium / low based on language used
            (crash/down/urgent = critical, broken/failing = high, improvement = medium, typo/doc = low)
          Assignee suggestion: leave blank (no assignee data available)
Step 4 — Call update_issue(project_id, issue_iid, labels=[...]) to apply labels
Step 5 — Call create_issue_note(project_id, issue_iid, body=...) with:

  🤖 **DevFlow Auto-Triage**
  **Labels applied:** label1, label2
  **Suggested priority:** High
  **Summary:** One sentence describing what this issue is about.
  **Suggested next step:** One concrete action the team should take.
  *Powered by DevFlow Agent*

Step 6 — Return: "Issue #X triaged. Labels: [...]. Priority: X."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## 4. DAILY DIGEST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

When asked for a daily digest:

Step 1 — Call list_merge_requests(project_id, state="opened") — get all open MRs
Step 2 — Identify stale MRs (updated_at > 2 days ago, date provided in prompt)
Step 3 — Call list_issues(project_id, state="opened") — get open issues count
Step 4 — Call get_leaderboard() — get current top 5
Step 5 — Output a formatted markdown digest:

  # DevFlow Daily Digest — DATE
  **Project:** project_id

  ## Open MRs (N total)
  List each: MR #X — Title — Author — X days since update

  ## Stale MRs (N)
  List each stale one with days inactive

  ## Open Issues
  Total count + any critical ones

  ## Leaderboard (Top 5)
  Rank | Developer | Points | MRs

  ## Team Health
  One paragraph summary: overall team velocity, bottlenecks, recommendations.
"""

# ── Agent ─────────────────────────────────────────────────────────────────────

agent = LlmAgent(
    model="gemini-2.5-flash",
    name="devflow_agent",
    instruction=INSTRUCTION,
    tools=[
        gitlab_mcp,
        FunctionTool(save_score),
        FunctionTool(get_leaderboard),
    ],
)

# ── Runner ────────────────────────────────────────────────────────────────────

async def main():
    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="devflow", user_id="dev_1"
    )
    runner = Runner(
        agent=agent,
        app_name="devflow",
        session_service=session_service,
    )

    print("DevFlow Agent ready.\n")

    test_prompt = "Score merge request #1 in project smr_92/devpost_sample_project, then show the leaderboard"

    async for event in runner.run_async(
        user_id="dev_1",
        session_id=session.id,
        new_message=types.Content(
            role="user",
            parts=[types.Part(text=test_prompt)]
        )
    ):
        if hasattr(event, "content") and event.content and event.content.parts:
            for part in event.content.parts:
                if hasattr(part, "text") and part.text:
                    print(part.text)

if __name__ == "__main__":
    asyncio.run(main())
