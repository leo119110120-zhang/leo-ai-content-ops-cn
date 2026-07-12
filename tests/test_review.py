import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from content_ops.config import load_yaml, save_yaml
from content_ops.models import ContentStatus
from content_ops.review import build_review_model, render_review
from content_ops.server import apply_review_action, build_server, record_review_start
from content_ops.storage import transition


def make_review_task(root: Path) -> Path:
    task = root / "task"
    (task / "images").mkdir(parents=True)
    save_yaml(
        task / "manifest.yaml",
        {
            "content_id": "leo-test",
            "title": "测试",
            "status": "awaiting_review",
            "score": {"demand_timeliness": 21, "total": 83},
            "demand_evidence": ["评论区多次出现求部署"],
            "differentiation": "区分免费互动与真实付款证据",
            "packaging": {
                "titles": ["1", "2", "3", "4", "5"],
                "covers": ["a", "b", "c"],
                "openings": ["a", "b"],
                "reader_payoff": "收益",
                "discussion_question": "问题",
            },
            "sources": [
                {"id": "s1", "kind": "wiki", "path": "wiki/example.md"}
            ],
            "history": [],
        },
    )
    for name in (
        "03-wechat-final.md",
        "04-xhs-final.md",
        "05-quality-report.md",
    ):
        (task / name).write_text("# 可复制正文\n内容", encoding="utf-8")
    (task / "images" / "xhs-01.png").write_bytes(b"image")
    return task


class ReviewTests(unittest.TestCase):
    def test_review_contains_growth_evidence_and_controls(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = make_review_task(Path(tmp))
            model = build_review_model(task)
            self.assertEqual(len(model["titles"]), 5)
            output = render_review(task, task / "review.html")
            html = output.read_text(encoding="utf-8")
            self.assertIn("一键复制", html)
            self.assertIn("下载全部图片", html)
            self.assertIn("wiki/example.md", html)
            self.assertIn("评论区多次出现求部署", html)
            self.assertIn("83", html)
            self.assertIn('data-action="approve"', html)
            self.assertTrue((task / "images.zip").exists())

    def test_approve_updates_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = make_review_task(Path(tmp))
            message = apply_review_action(task, "approve", "")
            self.assertEqual(message, "审核状态已保存")
            self.assertEqual(load_yaml(task / "manifest.yaml")["status"], "approved")

    def test_revision_requires_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = make_review_task(Path(tmp))
            with self.assertRaisesRegex(ValueError, "必须填写理由"):
                apply_review_action(task, "revise", "")

    def test_review_timing_is_recorded_automatically(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = make_review_task(Path(tmp))
            started = datetime(2026, 7, 12, 5, 0, tzinfo=timezone.utc)
            finished = datetime(2026, 7, 12, 5, 2, 30, tzinfo=timezone.utc)
            record_review_start(task, now=started)
            record_review_start(
                task,
                now=datetime(2026, 7, 12, 5, 1, tzinfo=timezone.utc),
            )
            apply_review_action(task, "approve", "", now=finished)
            manifest = load_yaml(task / "manifest.yaml")
            self.assertEqual(
                manifest["review_started_at"], started.isoformat()
            )
            self.assertEqual(
                manifest["review_completed_at"], finished.isoformat()
            )
            self.assertEqual(manifest["review_duration_seconds"], 150)
            self.assertEqual(len(manifest["review_sessions"]), 1)
            self.assertEqual(manifest["review_sessions"][0]["action"], "approve")

    def test_revision_starts_a_new_review_session_without_losing_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = make_review_task(Path(tmp))
            first_start = datetime(2026, 7, 12, 5, 0, tzinfo=timezone.utc)
            first_finish = datetime(2026, 7, 12, 5, 4, tzinfo=timezone.utc)
            record_review_start(task, now=first_start)
            apply_review_action(
                task,
                "revise",
                "视觉不够吸引人",
                now=first_finish,
            )
            transition(task, ContentStatus.DRAFTING, "redesign")
            transition(task, ContentStatus.QA_PASSED, "qa passed")
            transition(task, ContentStatus.AWAITING_REVIEW, "ready again")

            second_start = datetime(2026, 7, 12, 6, 0, tzinfo=timezone.utc)
            second_finish = datetime(2026, 7, 12, 6, 1, tzinfo=timezone.utc)
            record_review_start(task, now=second_start)
            apply_review_action(task, "approve", now=second_finish)

            manifest = load_yaml(task / "manifest.yaml")
            self.assertEqual(len(manifest["review_sessions"]), 2)
            self.assertEqual(
                [session["action"] for session in manifest["review_sessions"]],
                ["revise", "approve"],
            )
            self.assertEqual(manifest["review_started_at"], second_start.isoformat())
            self.assertEqual(manifest["review_duration_seconds"], 60)

    def test_duplicate_approval_does_not_create_dangling_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = make_review_task(Path(tmp))
            started = datetime(2026, 7, 12, 5, 0, tzinfo=timezone.utc)
            finished = datetime(2026, 7, 12, 5, 1, tzinfo=timezone.utc)
            record_review_start(task, now=started)
            apply_review_action(task, "approve", now=finished)
            before = load_yaml(task / "manifest.yaml")

            with self.assertRaisesRegex(ValueError, "illegal transition"):
                apply_review_action(
                    task,
                    "approve",
                    now=datetime(2026, 7, 12, 5, 2, tzinfo=timezone.utc),
                )

            after = load_yaml(task / "manifest.yaml")
            self.assertEqual(after["review_sessions"], before["review_sessions"])

    def test_http_approve_action_updates_real_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = make_review_task(Path(tmp))
            server = build_server(task, 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                port = server.server_address[1]
                request = Request(
                    f"http://127.0.0.1:{port}/api/action",
                    data=b'{"action":"approve","note":""}',
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(request, timeout=3) as response:
                    self.assertEqual(response.status, 200)
                self.assertEqual(
                    load_yaml(task / "manifest.yaml")["status"], "approved"
                )
                thread.join(timeout=2)
                self.assertFalse(
                    thread.is_alive(),
                    "review server should release its port after a final action",
                )
            finally:
                if thread.is_alive():
                    server.shutdown()
                server.server_close()
                thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
