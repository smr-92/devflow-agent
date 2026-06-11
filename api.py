import os
import threading
from flask import Flask, jsonify, request, send_from_directory
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

def _run_worker(prompt: str, tag: str) -> None:
    """Run worker.py as a subprocess with a prompt string."""
    import subprocess, sys
    worker = os.path.join(os.path.dirname(__file__), "worker.py")
    proc = subprocess.Popen(
        [sys.executable, worker, prompt],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    for line in proc.stdout:
        print(f"[{tag}] {line.rstrip()[:160]}", flush=True)
    proc.wait()
    if proc.returncode != 0:
        print(f"[{tag}] worker exited with code {proc.returncode}", flush=True)


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
            target=_run_worker,
            args=(prompt, f"MR!{mr_iid}"),
            daemon=True,
        )
        t.start()
        return jsonify({"status": "scoring triggered", "project": project_id, "mr_iid": mr_iid}), 202

    # ── Issue / Work Item opened → auto-triage ───────────────────────────────
    if kind in ("issue", "work_item") and action == "open":
        project_id = payload["project"]["path_with_namespace"]
        issue_iid  = attrs.get("iid") or attrs.get("id")
        prompt = (
            f"Triage issue #{issue_iid} in project {project_id}. "
            f"Apply appropriate labels and post a triage comment."
        )
        print(f"[webhook] Issue opened — triaging {project_id} #{issue_iid}")
        t = threading.Thread(
            target=_run_worker,
            args=(prompt, f"Issue#{issue_iid}"),
            daemon=True,
        )
        t.start()
        return jsonify({"status": "triage triggered", "project": project_id, "issue_iid": issue_iid}), 202

    return jsonify({"status": "ignored", "kind": kind, "action": action}), 200


# ── Serve React frontend (catch-all) ──────────────────────────────────────────

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend", "dist")

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_frontend(path):
    if path and os.path.exists(os.path.join(FRONTEND_DIR, path)):
        return send_from_directory(FRONTEND_DIR, path)
    return send_from_directory(FRONTEND_DIR, "index.html")


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
