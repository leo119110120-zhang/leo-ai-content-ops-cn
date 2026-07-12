from pathlib import Path
import shutil

from content_ops.storage import load_manifest


def export_publish_package(task_dir: Path, output_root: Path) -> Path:
    manifest = load_manifest(task_dir)
    if manifest["status"] != "approved":
        raise ValueError("task must be approved before export")
    package = output_root / manifest["content_id"]
    if package.exists():
        raise FileExistsError(f"publish package already exists: {package}")
    (package / "images").mkdir(parents=True)
    shutil.copy2(
        task_dir / "03-wechat-final.md", package / "微信公众号.md"
    )
    shutil.copy2(task_dir / "04-xhs-final.md", package / "小红书.md")
    shutil.copy2(task_dir / "05-quality-report.md", package / "质量报告.md")
    shutil.copy2(task_dir / "manifest.yaml", package / "manifest.yaml")
    for image in (task_dir / "images").glob("*.png"):
        shutil.copy2(image, package / "images" / image.name)
    checklist = """# 发布前检查清单

- [ ] 标题与正文承诺一致
- [ ] 图片顺序正确且没有错字、截断
- [ ] 人名、手机号、账号、聊天截图已经脱敏
- [ ] 数据、价格、产品能力和平台规则仍然有效
- [ ] AI示意图没有被描述为真实客户或真实结果
- [ ] 小红书话题与正文相关，没有机械求赞收藏
- [ ] 公众号排版在手机预览中正常
- [ ] 发布后把链接和发布时间写回原任务的 manifest.yaml
"""
    (package / "发布前检查清单.md").write_text(
        checklist, encoding="utf-8"
    )
    return package
