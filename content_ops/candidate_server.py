from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading

from content_ops.candidate_review import render_candidates
from content_ops.candidates import CandidateBatchStore
from content_ops.config import load_yaml


def apply_candidate_action(
    batch_path: Path,
    action: str,
    candidate_id: str,
    on_selected,
    action_lock: threading.Lock,
) -> str:
    if action != "select":
        raise ValueError("unknown candidate action")
    with action_lock:
        before = load_yaml(batch_path)
        CandidateBatchStore(batch_path).select(candidate_id)
        should_start = before.get("status") == "awaiting_topic_selection"
    if should_start:
        threading.Thread(
            target=on_selected,
            args=(batch_path, candidate_id),
            daemon=True,
        ).start()
        return "选题已确认，正在生成内容"
    return "该选题已确认，无需重复提交"


class CandidateHandler(BaseHTTPRequestHandler):
    batch_path: Path
    output_path: Path
    on_selected = None
    action_lock: threading.Lock

    def do_GET(self):
        if self.path not in {"/", "/candidates.html"}:
            self.send_error(404)
            return
        render_candidates(self.batch_path, self.output_path)
        body = self.output_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/api/candidate-action":
            self.send_error(404)
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size > 16384:
                raise ValueError("request body is too large")
            payload = json.loads(self.rfile.read(size) or b"{}")
            message = apply_candidate_action(
                self.batch_path,
                str(payload.get("action", "")),
                str(payload.get("candidate_id", "")),
                self.on_selected,
                self.action_lock,
            )
            render_candidates(self.batch_path, self.output_path)
        except (ValueError, json.JSONDecodeError) as error:
            self._json(400, {"message": str(error)})
            return
        except Exception:
            self._json(500, {"message": "候选操作失败，请查看本地日志"})
            return
        self._json(200, {"message": message})

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return None


def build_candidate_server(
    batch_path: Path,
    port: int,
    on_selected,
) -> ThreadingHTTPServer:
    batch_path = batch_path.resolve()
    output_path = batch_path.with_suffix(".html")
    render_candidates(batch_path, output_path)
    handler_class = type(
        "LocalCandidateHandler",
        (CandidateHandler,),
        {
            "batch_path": batch_path,
            "output_path": output_path,
            "on_selected": staticmethod(on_selected),
            "action_lock": threading.Lock(),
        },
    )
    server = ThreadingHTTPServer(("127.0.0.1", port), handler_class)
    server.daemon_threads = True
    return server
