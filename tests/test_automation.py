import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from content_ops.automation import run_daily
from content_ops.config import save_yaml
from content_ops.providers import ModelResult, ModelUsage


class SpyModel:
    def __init__(self):
        self.calls = 0

    def complete_json(self, **kwargs):
        self.calls += 1
        raise AssertionError("model call was not expected")


class NoCandidateModel:
    def __init__(self):
        self.calls = 0

    def complete_json(self, **kwargs):
        self.calls += 1
        return ModelResult(
            {"candidates": []}, ModelUsage(10, 2), "fake"
        )


class FailingModel:
    def complete_json(self, **kwargs):
        raise RuntimeError("provider unavailable")


class AutomationTests(unittest.TestCase):
    def test_existing_awaiting_review_blocks_model_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task = root / "content-ops" / "drafts" / "task"
            task.mkdir(parents=True)
            (task / "manifest.yaml").write_text(
                "status: awaiting_review\n", encoding="utf-8"
            )
            model = SpyModel()

            outcome = run_daily(
                root,
                "2026-07-13",
                model,
                datetime(2026, 7, 13, 2, 30, tzinfo=timezone.utc),
            )

            self.assertEqual(outcome.status, "waiting_for_human")
            self.assertEqual(model.calls, 0)

    def test_pending_candidate_returns_page_for_server_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidates = root / "content-ops" / "candidates"
            candidates.mkdir(parents=True)
            batch = candidates / "2026-07-12.yaml"
            save_yaml(
                batch,
                {
                    "run_date": "2026-07-12",
                    "status": "awaiting_topic_selection",
                    "candidates": [],
                },
            )
            model = SpyModel()

            outcome = run_daily(
                root,
                "2026-07-13",
                model,
                datetime(2026, 7, 13, 2, 30, tzinfo=timezone.utc),
            )

            self.assertEqual(outcome.status, "waiting_for_human")
            self.assertEqual(
                outcome.artifact,
                (candidates / "2026-07-12.html").resolve(),
            )
            self.assertTrue(outcome.artifact.exists())
            self.assertEqual(model.calls, 0)

    def test_completed_date_does_not_run_twice(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "content-ops" / "state"
            state.mkdir(parents=True)
            (state / "daily-2026-07-13.done").write_text(
                "status: complete\n", encoding="utf-8"
            )
            model = SpyModel()

            outcome = run_daily(
                root,
                "2026-07-13",
                model,
                datetime(2026, 7, 13, 3, 0, tzinfo=timezone.utc),
            )

            self.assertEqual(outcome.status, "already_ran")
            self.assertEqual(model.calls, 0)

    def test_stale_lock_is_recovered_but_recent_lock_is_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "content-ops" / "state"
            state.mkdir(parents=True)
            lock = state / "daily-2026-07-13.lock"
            save_yaml(lock, {"started_at": "2026-07-13T00:00:00+00:00"})
            model = NoCandidateModel()

            outcome = run_daily(
                root,
                "2026-07-13",
                model,
                datetime(2026, 7, 13, 3, 0, tzinfo=timezone.utc),
            )

            self.assertEqual(outcome.status, "no_candidates")
            self.assertEqual(model.calls, 1)

            recent_lock = state / "daily-2026-07-14.lock"
            save_yaml(
                recent_lock,
                {"started_at": "2026-07-14T02:59:00+00:00"},
            )
            recent = run_daily(
                root,
                "2026-07-14",
                model,
                datetime(2026, 7, 14, 3, 0, tzinfo=timezone.utc),
            )
            self.assertEqual(recent.status, "already_running")

    def test_malformed_pending_manifest_blocks_instead_of_being_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task = root / "content-ops" / "drafts" / "task"
            task.mkdir(parents=True)
            (task / "manifest.yaml").write_text("- not-a-map\n", encoding="utf-8")
            model = SpyModel()

            outcome = run_daily(
                root,
                "2026-07-13",
                model,
                datetime(2026, 7, 13, 3, 0, tzinfo=timezone.utc),
            )

            self.assertEqual(outcome.status, "waiting_for_human")
            self.assertEqual(model.calls, 0)

    def test_model_failure_rolls_back_source_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "wiki").mkdir()
            (root / "wiki" / "new.md").write_text(
                "一条还没有处理的新来源", encoding="utf-8"
            )
            state = root / "content-ops" / "state"

            with self.assertRaisesRegex(RuntimeError, "provider unavailable"):
                run_daily(
                    root,
                    "2026-07-13",
                    FailingModel(),
                    datetime(2026, 7, 13, 3, 0, tzinfo=timezone.utc),
                )

            self.assertFalse((state / "source-cache.yaml").exists())
            self.assertFalse((state / "daily-2026-07-13.done").exists())
