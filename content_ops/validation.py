from pathlib import Path
import shutil

from content_ops.packaging import export_publish_package
from content_ops.server import apply_review_action
from content_ops.storage import load_manifest


def validate_end_to_end(task_dir: Path, scratch_root: Path) -> dict:
    source_manifest = load_manifest(task_dir)
    if source_manifest["status"] != "awaiting_review":
        raise ValueError("source task must be awaiting_review")
    scratch_root.mkdir(parents=True, exist_ok=False)
    task_copy = scratch_root / "task"
    shutil.copytree(task_dir, task_copy)
    apply_review_action(task_copy, "approve", "isolated validation")
    package = export_publish_package(task_copy, scratch_root / "packages")
    required = {
        "微信公众号.md",
        "小红书.md",
        "质量报告.md",
        "manifest.yaml",
        "发布前检查清单.md",
    }
    missing = sorted(
        name for name in required if not (package / name).exists()
    )
    if missing:
        raise RuntimeError("package missing files: " + ", ".join(missing))
    images = sorted((package / "images").glob("*.png"))
    if not images:
        raise RuntimeError("package has no PNG images")
    source_after = load_manifest(task_dir)
    if source_after["status"] != source_manifest["status"]:
        raise RuntimeError("source task was mutated during validation")
    return {
        "source_status": source_after["status"],
        "copy_status": load_manifest(task_copy)["status"],
        "image_count": len(images),
        "package": package,
    }
