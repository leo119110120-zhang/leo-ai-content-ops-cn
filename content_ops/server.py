from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from datetime import datetime, timezone
import json
import threading

from content_ops.config import save_yaml
from content_ops.models import ContentStatus
from content_ops.review import render_review
from content_ops.storage import load_manifest, transition


def _legacy_review_session(manifest: dict) -> dict | None:
    started_at = manifest.get("review_started_at")
    if not started_at:
        return None
    session = {"started_at": started_at}
    if manifest.get("review_completed_at"):
        session["completed_at"] = manifest["review_completed_at"]
    if manifest.get("review_duration_seconds") is not None:
        session["duration_seconds"] = manifest["review_duration_seconds"]
    for event in reversed(manifest.get("history", [])):
        if event.get("from") != ContentStatus.AWAITING_REVIEW.value:
            continue
        actions = {
            ContentStatus.APPROVED.value: "approve",
            ContentStatus.REVISION_REQUESTED.value: "revise",
            ContentStatus.REJECTED.value: "reject",
        }
        action = actions.get(event.get("to"))
        if action:
            session["action"] = action
            session["note"] = event.get("note", "")
            break
    return session


def _review_sessions(manifest: dict) -> list[dict]:
    sessions = manifest.setdefault("review_sessions", [])
    if not sessions:
        legacy = _legacy_review_session(manifest)
        if legacy:
            sessions.append(legacy)
    return sessions


def record_review_start(
    task_dir: Path, now: datetime | None = None
) -> str:
    manifest = load_manifest(task_dir)
    if manifest.get("status") != ContentStatus.AWAITING_REVIEW.value:
        raise ValueError("content is not awaiting review")
    sessions = _review_sessions(manifest)
    if not sessions or sessions[-1].get("completed_at"):
        timestamp = (now or datetime.now(timezone.utc)).isoformat()
        sessions.append({"started_at": timestamp})
        manifest["review_started_at"] = timestamp
        manifest.pop("review_completed_at", None)
        manifest.pop("review_duration_seconds", None)
    else:
        manifest["review_started_at"] = sessions[-1]["started_at"]
    save_yaml(task_dir / "manifest.yaml", manifest)
    return "审核计时已开始"


def apply_review_action(
    task_dir: Path,
    action: str,
    note: str = "",
    now: datetime | None = None,
) -> str:
    targets = {
        "approve": ContentStatus.APPROVED,
        "revise": ContentStatus.REVISION_REQUESTED,
        "reject": ContentStatus.REJECTED,
    }
    if action not in targets:
        raise ValueError("未知审核动作")
    note = note.strip()
    if action in {"revise", "reject"} and not note:
        raise ValueError("退回或放弃必须填写理由")
    manifest = load_manifest(task_dir)
    current = manifest.get("status")
    if current != ContentStatus.AWAITING_REVIEW.value:
        raise ValueError(
            f"illegal transition: {current} -> {targets[action].value}"
        )
    completed = now or datetime.now(timezone.utc)
    sessions = _review_sessions(manifest)
    if not sessions or sessions[-1].get("completed_at"):
        sessions.append({"started_at": completed.isoformat()})
    save_yaml(task_dir / "manifest.yaml", manifest)
    transition(task_dir, targets[action], note)
    manifest = load_manifest(task_dir)
    sessions = _review_sessions(manifest)
    session = sessions[-1]
    session["completed_at"] = completed.isoformat()
    session["action"] = action
    session["note"] = note
    started = datetime.fromisoformat(session["started_at"])
    duration = max(0, int((completed - started).total_seconds()))
    session["duration_seconds"] = duration
    manifest["review_started_at"] = session["started_at"]
    manifest["review_completed_at"] = completed.isoformat()
    manifest["review_duration_seconds"] = duration
    save_yaml(task_dir / "manifest.yaml", manifest)
    return "审核状态已保存"


class ReviewHandler(SimpleHTTPRequestHandler):
    task_dir: Path

    def do_POST(self):
        if self.path not in {"/api/action", "/api/review-start"}:
            self.send_error(404)
            return
        size = int(self.headers.get("Content-Length", "0"))
        try:
            payload = json.loads(self.rfile.read(size) or b"{}")
            if self.path == "/api/review-start":
                message = record_review_start(self.task_dir)
                self._json(200, {"message": message})
                return
            message = apply_review_action(
                self.task_dir,
                str(payload.get("action", "")),
                str(payload.get("note", "")),
            )
            render_review(self.task_dir, self.task_dir / "review.html")
        except (ValueError, json.JSONDecodeError) as error:
            self._json(400, {"message": str(error)})
            return
        self._json(200, {"message": message})
        threading.Thread(target=self.server.shutdown, daemon=True).start()

    def _json(self, status: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def build_server(task_dir: Path, port: int = 8765) -> ThreadingHTTPServer:
    task_dir = task_dir.resolve()
    render_review(task_dir, task_dir / "review.html")
    handler_class = type(
        "TaskReviewHandler", (ReviewHandler,), {"task_dir": task_dir}
    )
    handler = partial(handler_class, directory=str(task_dir))
    return ThreadingHTTPServer(("127.0.0.1", port), handler)


def serve(task_dir: Path, port: int = 8765) -> None:
    server = build_server(task_dir, port)
    actual_port = server.server_address[1]
    print(f"Review center: http://127.0.0.1:{actual_port}/review.html")
    server.serve_forever()
