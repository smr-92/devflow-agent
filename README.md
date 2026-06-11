# DevFlow Agent

> An AI agent that actively manages your GitLab workspace — auto-triages issues, scores PR quality, detects stale MRs, posts review comments, and delivers daily team digests.

Built for the **Google Cloud Rapid Agent Hackathon** (GitLab Partner Track) using Google Cloud Agent Builder, Gemini 2.5 Flash, and the GitLab MCP server.

**Live demo:** https://devflow-api-474589882332.us-central1.run.app

---

## What It Does

### 🔔 Real-time Webhook Triggers
- **New MR opened** → agent automatically scores the PR (0-100), posts a detailed code review comment with score breakdown, change summary, and impact analysis
- **New issue opened** → agent auto-triages: applies labels, estimates priority, posts a triage comment with next steps

### 🔍 Stale MR Detection
Scans all open MRs, identifies ones with no activity for N days, and posts a nudge comment to the author. Run manually or schedule via Cloud Scheduler.

### 📊 Daily Team Digest
Generates a full markdown report covering open MRs, stale MRs, open issues, leaderboard snapshot, and a team health summary.

### 🏆 Developer Leaderboard Dashboard
Every scored PR feeds a persistent leaderboard:
- **Points** = PR Score × Complexity Multiplier (1.0 / 1.3 / 1.6)
- **Streak eligible** = score ≥ 70
- Real-time React dashboard showing rankings, MR history, and per-dimension score breakdowns

---

## PR Scoring Rubric

The agent evaluates each MR across 6 dimensions using the actual diff, description, and review activity:

| Dimension | Weight | What's Evaluated |
|---|---|---|
| Description Quality | 25% | Does it explain WHAT and WHY? Are testing steps included? |
| Code Clarity | 25% | Readable names, no smells, logical structure |
| Test Coverage Signal | 20% | Are test files present and meaningful? |
| PR Size Appropriateness | 15% | 1-10 files = ideal, 21+ = too large |
| Review Responsiveness | 10% | Did the author respond to comments? All threads resolved? |
| Iteration Quality | 5% | Clean commit history vs. "fix fix fix" commits |

**Points formula:** `score × multiplier` where multiplier is `1.0` (≤5 files), `1.3` (6-15 files), or `1.6` (16+ files)

---

## Architecture

```
GitLab Webhooks (MR open / Issue open)
         │
         ▼
  Flask API (api.py)  ──── REST endpoints ──── React Dashboard
         │                                      (localhost:5173)
         ▼
Google Cloud Agent Builder
  LlmAgent (Gemini 2.5 Flash via Vertex AI)
         │
    ┌────┴─────────────────────────┐
    ▼                              ▼
GitLab MCP Server              Firestore
(@zereight/mcp-gitlab)      (scores, leaderboard)
    │
    ├── list_merge_requests
    ├── get_merge_request
    ├── list_merge_request_diffs
    ├── list_merge_request_changed_files
    ├── get_merge_request_notes
    ├── create_merge_request_note
    ├── get_issue / update_issue
    ├── create_issue_note
    └── list_labels
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Agent Framework | Google Cloud Agent Builder (ADK 2.0) |
| LLM | Gemini 2.5 Flash via Vertex AI |
| GitLab Integration | `@zereight/mcp-gitlab` MCP server |
| Backend API | Flask + flask-cors |
| Database | Cloud Firestore (native mode) |
| Frontend | React + TypeScript + Tailwind CSS + Vite |
| Tunnel (dev) | ngrok |
| Deployment | Google Cloud Run |

---

## Project Structure

```
devflow-agent/
├── agent.py          # Core ADK agent — scoring, triage, stale detection, digest
├── api.py            # Flask server — REST API + GitLab webhook handler
├── worker.py         # Subprocess worker — runs agent for webhook events (Cloud Run safe)
├── stale.py          # CLI script — scan and notify stale MRs
├── digest.py         # CLI script — generate daily team digest
├── score_batch.py    # CLI script — batch score multiple MRs
├── Dockerfile        # Multi-stage build: Node.js 20 + Python 3.11
├── requirements.txt  # Python dependencies
└── frontend/
    └── src/
        ├── App.tsx
        ├── components/
        │   ├── Leaderboard.tsx   # Ranked developer table
        │   └── ScoreDetail.tsx   # Per-MR score detail with dimension bars
        └── types.ts
```

---

## Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- Google Cloud project with billing enabled
- GitLab account with a Personal Access Token (`api` scope)
- `gcloud` CLI authenticated (`gcloud auth application-default login`)

### 1. Clone and install

```bash
git clone https://github.com/YOUR_USERNAME/devflow-agent.git
cd devflow-agent
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

Create a `.env` file in the project root:

```env
GITLAB_TOKEN=glpat-xxxxxxxxxxxxxxxxxxxx
GITLAB_URL=https://gitlab.com
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GITLAB_WEBHOOK_SECRET=your-webhook-secret
GOOGLE_GENAI_USE_VERTEXAI=1
```

> **Note:** `GOOGLE_GENAI_USE_VERTEXAI=1` routes all LLM calls through Vertex AI using Application Default Credentials. No API key needed.

### 3. Enable GCP services

```bash
gcloud services enable aiplatform.googleapis.com firestore.googleapis.com --project=YOUR_PROJECT
gcloud firestore databases create --location=us-central1 --project=YOUR_PROJECT
```

### 4. Install the GitLab MCP server

```bash
npm install -g @zereight/mcp-gitlab
```

### 5. Install and start the frontend

```bash
cd frontend
npm install
npm run dev      # runs on http://localhost:5173
```

---

## Running Locally

### Start the API server

```bash
source venv/bin/activate
python api.py
# Flask running on http://localhost:8080
```

### Expose via ngrok (for webhook testing)

```bash
ngrok http 8080
# Copy the https://xxxx.ngrok-free.app URL
```

### Configure GitLab webhook

Go to: `gitlab.com/YOUR_NAMESPACE/YOUR_PROJECT/-/hooks`

| Field | Value |
|---|---|
| URL | `https://xxxx.ngrok-free.app/webhook` |
| Secret token | value from `.env` GITLAB_WEBHOOK_SECRET |
| Triggers | ✅ Merge request events + ✅ Work item events |

---

## CLI Scripts

### Score a single MR

```bash
python agent.py
# Edit test_prompt in main() or import agent and call directly
```

### Batch score multiple MRs

```bash
python score_batch.py 1 20
# Scores MRs #1 through #20 sequentially, saves to Firestore
```

### Detect and notify stale MRs

```bash
python stale.py your-namespace/your-project
# Optional: python stale.py your-namespace/your-project 5  (5-day threshold)
```

### Generate daily digest

```bash
python digest.py your-namespace/your-project
# Prints full markdown report to stdout
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/leaderboard` | Top 20 developers by total points |
| `GET` | `/api/scores/<username>` | All scored MRs for a developer |
| `POST` | `/webhook` | GitLab webhook receiver (MR + Issue events) |

### Webhook payload (GitLab sends automatically)

**MR opened** → agent scores + posts review comment
**Issue opened** → agent triages + applies labels + posts comment

Verify with `X-Gitlab-Token` header matching `GITLAB_WEBHOOK_SECRET`.

---

## Dashboard

Open [http://localhost:5173](http://localhost:5173) after starting the frontend.

- **Leaderboard** — ranked table with points bar, MR count, streak badges
- **Developer detail** — click any developer to see all their scored MRs with per-dimension progress bars and rationale

---

## Sample DevFlow Comment (MR Review)

```
🤖 DevFlow Code Review

## Score: 73/100 — 73 pts · small complexity · 🔥 Streak eligible!

| Dimension        | Score  | Notes                                              |
|------------------|--------|----------------------------------------------------|
| Description      | 90/100 | Full explanation of what and why                   |
| Code Clarity     | 85/100 | Clean logic, meaningful variable names             |
| Test Coverage    | 20/100 | No test files added — consider unit tests          |
| PR Size          | 100/100| Only 1 file changed — ideal scope                 |
| Review Response  | 50/100 | No comments yet (neutral)                          |
| Iteration Quality| 80/100 | Single clean commit                                |

## 📝 What Changed
- `auth/oauth.py` — Added mobile Safari user-agent detection before OAuth redirect
- `tests/` — No test coverage added for the new detection logic

## ⚠️ Potential Impact
- OAuth flow on mobile Safari will now redirect differently — regression test recommended
- User-agent detection is brittle; consider feature detection instead
- Missing tests for the critical path added in this MR

---
*Powered by DevFlow Agent*
```

---

## Firestore Data Model

```
scores/
  {project_id}_{mr_iid}/
    project_id, mr_iid, title, author
    total_score, complexity, complexity_multiplier, points
    streak_eligible, scored_at
    dimensions/
      description_quality: { score, weighted, rationale }
      code_clarity:         { score, weighted, rationale }
      ...

developers/
  {username}/
    username, total_points, mr_count
    streak_eligible_count, last_scored_at
```

---

## Hackathon Context

**Event:** Google Cloud Rapid Agent Hackathon (Devpost)
**Track:** GitLab Partner Track
**Deadline:** June 11, 2026

**Key requirements met:**
- ✅ Google Cloud Agent Builder (ADK 2.0) as the agent framework
- ✅ Gemini 2.5 Flash via Vertex AI as the LLM
- ✅ GitLab partner MCP server (`@zereight/mcp-gitlab`) for all GitLab operations
- ✅ Cloud Firestore for persistence
- ✅ Real-time webhook integration

---

## License

MIT
