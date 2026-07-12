import tempfile
import unittest
from pathlib import Path

from content_ops.models import ContentStatus
from content_ops.storage import create_task, load_manifest, transition


ELIGIBLE = {
    "id": "pilot",
    "title": "测试选题",
    "category": "adjacent_broad",
    "trigger": "用户正尝试判断AI内容是否能变现",
    "audience": "AI内容创作者",
    "demand_evidence": ["多次出现同类提问"],
    "differentiation": "区分互动和付费",
    "scores": {
        "demand_timeliness": 20,
        "hook_strength": 16,
        "consumption_value": 16,
        "evidence": 12,
        "differentiation": 7,
        "account_fit": 7,
    },
}


class StorageTests(unittest.TestCase):
    def test_create_task_writes_required_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = create_task(Path(tmp), ELIGIBLE, "2026-07-12")
            self.assertTrue((task / "manifest.yaml").exists())
            self.assertTrue((task / "images").is_dir())
            manifest = load_manifest(task)
            self.assertEqual(manifest["status"], "researching")
            self.assertEqual(manifest["demand_evidence"], ["多次出现同类提问"])

    def test_illegal_transition_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = create_task(Path(tmp), ELIGIBLE, "2026-07-12")
            with self.assertRaisesRegex(ValueError, "researching -> approved"):
                transition(task, ContentStatus.APPROVED)

    def test_valid_transition_is_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = create_task(Path(tmp), ELIGIBLE, "2026-07-12")
            manifest = transition(
                task, ContentStatus.DRAFTING, "source pack ready"
            )
            self.assertEqual(manifest["status"], "drafting")
            self.assertEqual(manifest["history"][-1]["note"], "source pack ready")


if __name__ == "__main__":
    unittest.main()
