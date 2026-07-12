import tempfile
import unittest
from pathlib import Path

from PIL import Image

from content_ops.config import load_yaml, save_yaml
from content_ops.quality import run_quality_checks


def make_task(root: Path) -> Path:
    task = root / "task"
    (task / "images").mkdir(parents=True)
    save_yaml(
        task / "manifest.yaml",
        {
            "content_id": "leo-test",
            "status": "drafting",
            "sources": [
                {"id": "s1", "kind": "wiki", "path": "wiki/example.md"}
            ],
            "claims": [
                {
                    "text": "真实内容与来源说明。",
                    "label": "verified",
                    "source_ids": ["s1"],
                }
            ],
            "packaging": {
                "titles": ["a", "b", "c", "d", "e"],
                "covers": ["a", "b", "c"],
                "openings": ["a", "b"],
                "reader_payoff": "看完能判断评论热度是否等于付费需求",
                "discussion_question": "你会先看领取数，还是先看付款？",
            },
            "xhs_cards": [
                {
                    "eyebrow": "测试",
                    "title": "有效标题",
                    "body": "有效正文",
                }
            ],
        },
    )
    content = {
        "00-brief.md": "# 选题说明\n这是一篇需求优先的选题说明。\n",
        "01-source-pack.md": "# 资料与来源\n事实、推断和未知内容分别记录。\n",
        "02-master-draft.md": "# 内容母稿\n这里保存完整论证链与行动建议。\n",
        "03-wechat-final.md": "# 公众号终稿\n长文解释证据层级和七天验证流程。\n",
        "04-xhs-final.md": "# 小红书终稿\n86条评论不等于有人付款，先看预付款。\n",
    }
    for name, text in content.items():
        (task / name).write_text(text, encoding="utf-8")
    Image.new("RGB", (900, 383), "white").save(
        task / "images" / "wechat-cover.png"
    )
    Image.new("RGB", (1080, 1350), "white").save(
        task / "images" / "xhs-01.png"
    )
    return task


class QualityTests(unittest.TestCase):
    def test_valid_task_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = run_quality_checks(make_task(Path(tmp)))
            self.assertTrue(report.passed, [item.message for item in report.items])

    def test_missing_source_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = make_task(Path(tmp))
            manifest = load_yaml(task / "manifest.yaml")
            manifest["sources"] = []
            save_yaml(task / "manifest.yaml", manifest)
            report = run_quality_checks(task)
            self.assertIn("sources.empty", [item.code for item in report.items])
            self.assertIn("claims.unlinked", [item.code for item in report.items])

    def test_phone_number_is_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = make_task(Path(tmp))
            test_phone = "138" + "1234" + "5678"
            (task / "04-xhs-final.md").write_text(
                f"联系我：{test_phone}", encoding="utf-8"
            )
            report = run_quality_checks(task)
            self.assertIn("privacy.phone", [item.code for item in report.items])

    def test_current_web_source_requires_retrieval_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = make_task(Path(tmp))
            manifest = load_yaml(task / "manifest.yaml")
            manifest["sources"].append(
                {
                    "id": "s2",
                    "kind": "web",
                    "url": "https://example.com/platform-rule",
                    "current": True,
                }
            )
            save_yaml(task / "manifest.yaml", manifest)
            report = run_quality_checks(task)
            self.assertIn(
                "sources.retrieved_at", [item.code for item in report.items]
            )

    def test_identical_platform_copy_is_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = make_task(Path(tmp))
            same = "# 完全相同的稿件\n直接复制不算平台原生适配。"
            (task / "03-wechat-final.md").write_text(same, encoding="utf-8")
            (task / "04-xhs-final.md").write_text(same, encoding="utf-8")
            report = run_quality_checks(task)
            self.assertIn(
                "platforms.identical", [item.code for item in report.items]
            )

    def test_invalid_png_is_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = make_task(Path(tmp))
            (task / "images" / "xhs-01.png").write_bytes(b"not-a-png")
            report = run_quality_checks(task)
            self.assertIn("assets.invalid", [item.code for item in report.items])

    def test_wrong_platform_dimensions_are_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = make_task(Path(tmp))
            Image.new("RGB", (800, 800), "white").save(
                task / "images" / "xhs-01.png"
            )
            report = run_quality_checks(task)
            self.assertIn(
                "assets.dimensions", [item.code for item in report.items]
            )

    def test_card_script_count_must_match_generated_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = make_task(Path(tmp))
            manifest = load_yaml(task / "manifest.yaml")
            manifest["xhs_cards"].append(
                {"eyebrow": "第二张", "title": "另一标题", "body": "另一正文"}
            )
            save_yaml(task / "manifest.yaml", manifest)
            report = run_quality_checks(task)
            self.assertIn("assets.card_count", [item.code for item in report.items])


if __name__ == "__main__":
    unittest.main()
