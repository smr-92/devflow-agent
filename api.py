import asyncio
import os
import threading
from flask import Flask, jsonify, request
from flask_cors import CORS
from google.cloud import firestore
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

db = firestore.Client(project=os.getenv("GOOGLE_CLOUD_PROJECT", "devflow-agent"))


# ── REST endpoints ────────────────────────────────────────────────────────────

@app.route("/api/leaderboard")
def leaderboard():
    docs = (
        db.collection("developers")
        .order_by("total_points", direction=firestore.Query.DESCENDING)
        .limit(20)
        .stream()
    )
    result = []
    for i, d in enumerate(docs):
        data = d.to_dict()
        if "last_scored_at" in data:
            data["last_scored_at"] = data["last_scored_at"].isoformat()
        result.append({"rank": i + 1, "id": d.id, **data})
    return jsonify(result)


@app.route("/api/scores/<username>")
def scores(username):
    docs = db.collection("scores").where("author", "==", username).stream()
    result = []
    for d in docs:
        data = d.to_dict()
        if "scored_at" in data:
            data["scored_at"] = data["scored_at"].isoformat()
        result.append({"id": d.id, **data})
    result.sort(key=lambda x: x.get("scored_at", ""), reverse=True)
    return jsonify(result)


# ── Webhook ───────────────────────────────────────────────────────────────────

def _run_agent_in_background(user_id: str, prompt: str, tag: str) -> None:
    """Spin up a fresh event loop in a daemon thread to run the agent."""
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types
    from agent import agent

    async def _run():
        session_service = InMemorySessionService()
        session = await session_service.create_session(app_name="devflow", user_id=user_id)
        runner = Runner(agent=agent, app_name="devflow", session_service=session_service)
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session.id,
            new_message=types.Content(role="user", parts=[types.Part(text=prompt)])
        ):
            if hasattr(event, "content") and event.content and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        print(f"[{tag}] {part.text[:140]}")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_run())
    finally:
        loop.close()


@app.route("/webhook", methods=["POST"])
def gitlab_webhook():
    token    = request.headers.get("X-Gitlab-Token", "")
    expected = os.getenv("GITLAB_WEBHOOK_SECRET", "")
    if expected and token != expected:
        return jsonify({"error": "unauthorized"}), 401

    payload = request.get_json(silent=True) or {}
    kind    = payload.get("object_kind")
    attrs   = payload.get("object_attributes", {})
    action  = attrs.get("action")

    # ── Merge request opened → score + comment ────────────────────────────────
    if kind == "merge_request" and action == "open":
        project_id = payload["project"]["path_with_namespace"]
        mr_iid     = attrs["iid"]
        prompt = (
            f"Score merge request #{mr_iid} in project {project_id}, "
            f"save the score, then post a comment on the MR summarising the score."
        )
        print(f"[webhook] MR opened — scoring {project_id} !{mr_iid}")
        t = threading.Thread(
            target=_run_agent_in_background,
            args=("webhook_mr", prompt, f"MR!{mr_iid}"),
            daemon=True,
        )
        t.start()
        return jsonify({"status": "scoring triggered", "project": project_id, "mr_iid": mr_iid}), 202

    # ── Issue opened → auto-triage ────────────────────────────────────────────
    if kind == "issue" and action == "open":
        project_id  = payload["project"]["path_with_namespace"]
        issue_iid   = attrs["iid"]
        prompt = (
            f"Triage issue #{issue_iid} in project {project_id}. "
            f"Apply appropriate labels and post a triage comment."
        )
        print(f"[webhook] Issue opened — triaging {project_id} #{issue_iid}")
        t = threading.Thread(
            target=_run_agent_in_background,
            args=("webhook_issue", prompt, f"Issue#{issue_iid}"),
            daemon=True,
        )
        t.start()
        return jsonify({"status": "triage triggered", "project": project_id, "issue_iid": issue_iid}), 202

    return jsonify({"status": "ignored", "kind": kind, "action": action}), 200


if __name__ == "__main__":
    app.run(debug=True, port=8080, use_reloader=False)
