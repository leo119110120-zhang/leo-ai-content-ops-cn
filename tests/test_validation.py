import tempfile
import unittest
from pathlib import Path

from content_ops.config import load_yaml, save_yaml
from content_ops.validation import validate_end_to_end


def make_pilot(root: Path) -> Path:
    task = root / "pilot"
    (task / "images").mkdir(parents=True)
    save_yaml(
        task / "manifest.yaml",
        {
            "content_id": "leo-pilot",
            "status": "awaiting_review",
            "history": [],
        },
    )
    for name in (
        "03-wechat-final.md",
        "04-xhs-final.md",
        "05-quality-report.md",
    ):
        (task / name).write_text("final", encoding="utf-8")
    (task / "images" / "wechat-cover.png").write_bytes(b"cover")
    (task / "images" / "xhs-01.png").write_bytes(b"card")
    return task


class ValidationTests(unittest.TestCase):
    def test_realistic_copy_can_be_approved_and_exported_without_mutating_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task = make_pilot(root)
            result = validate_end_to_end(task, root / "scratch")
            self.assertEqual(result["source_status"], "awaiting_review")
            self.assertEqual(result["copy_status"], "approved")
            self.assertEqual(result["image_count"], 2)
            self.assertTrue(result["package"].exists())
            self.assertEqual(
                load_yaml(task / "manifest.yaml")["status"],
                "awaiting_review",
            )


if __name__ == "__main__":
    unittest.main()
