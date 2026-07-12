import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from content_ops.candidate_review import render_candidates
from content_ops.candidate_server import build_candidate_server
from content_ops.config import save_yaml


def batch_data():
    return {
        "run_date": "2026-07-13",
        "status": "awaiting_topic_selection",
        "candidates": [
            {
                "id": "a",
                "title": "评论很多不等于有人付款",
                "trigger": "评论区反复询问部署文档",
                "audience": "想用AI做内容副业的人",
                "demand_evidence": ["评论重复询问", "问题具体可执行"],
                "differentiation": "区分互动、询单和付款证据",
                "risks": ["不得虚构成交"],
                "scores": {"total": 83, "demand_timeliness": 21},
            }
        ],
    }


class CandidateServerTests(unittest.TestCase):
    def test_page_shows_evidence_scores_and_actions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch = root / "batch.yaml"
            save_yaml(batch, batch_data())

            page = render_candidates(batch, root / "candidates.html")

            html = page.read_text(encoding="utf-8")
            self.assertIn("评论重复询问", html)
            self.assertIn("83", html)
            self.assertIn('data-candidate-id="a"', html)

    def test_select_post_is_idempotent_and_calls_callback_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch = root / "batch.yaml"
            save_yaml(batch, batch_data())
            calls = []
            called = threading.Event()

            def callback(path, candidate_id):
                calls.append(candidate_id)
                called.set()

            server = build_candidate_server(batch, 0, callback)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                port = server.server_address[1]
                body = json.dumps(
                    {"action": "select", "candidate_id": "a"}
                ).encode()
                for _ in range(2):
                    request = Request(
                        f"http://127.0.0.1:{port}/api/candidate-action",
                        data=body,
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    with urlopen(request, timeout=3) as response:
                        self.assertEqual(response.status, 200)
                self.assertTrue(called.wait(2))
                self.assertEqual(calls, ["a"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)

    def test_unknown_action_returns_400_without_callback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch = root / "batch.yaml"
            save_yaml(batch, batch_data())
            called = threading.Event()
            server = build_candidate_server(
                batch, 0, lambda path, candidate_id: called.set()
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                port = server.server_address[1]
                request = Request(
                    f"http://127.0.0.1:{port}/api/candidate-action",
                    data=json.dumps(
                        {"action": "delete", "candidate_id": "a"}
                    ).encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with self.assertRaises(HTTPError) as error:
                    urlopen(request, timeout=3)
                self.assertEqual(error.exception.code, 400)
                self.assertFalse(called.is_set())
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)
