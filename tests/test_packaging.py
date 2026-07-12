import tempfile
import unittest
from pathlib import Path

from content_ops.config import save_yaml
from content_ops.packaging import export_publish_package


def make_task(root: Path, status: str) -> Path:
    task = root / "task"
    (task / "images").mkdir(parents=True)
    save_yaml(
        task / "manifest.yaml",
        {"content_id": "leo-test", "status": status},
    )
    for name in (
        "03-wechat-final.md",
        "04-xhs-final.md",
        "05-quality-report.md",
    ):
        (task / name).write_text("final", encoding="utf-8")
    (task / "images" / "xhs-01.png").write_bytes(b"png")
    return task


class PackagingTests(unittest.TestCase):
    def test_only_approved_task_can_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = make_task(Path(tmp), "awaiting_review")
            with self.assertRaisesRegex(ValueError, "approved"):
                export_publish_package(task, Path(tmp) / "packages")

    def test_export_contains_copy_images_and_checklist(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = make_task(Path(tmp), "approved")
            package = export_publish_package(task, Path(tmp) / "packages")
            self.assertTrue((package / "微信公众号.md").exists())
            self.assertTrue((package / "小红书.md").exists())
            self.assertTrue((package / "发布前检查清单.md").exists())
            self.assertTrue((package / "images" / "xhs-01.png").exists())

    def test_existing_package_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = make_task(Path(tmp), "approved")
            output = Path(tmp) / "packages"
            export_publish_package(task, output)
            with self.assertRaises(FileExistsError):
                export_publish_package(task, output)


if __name__ == "__main__":
    unittest.main()
