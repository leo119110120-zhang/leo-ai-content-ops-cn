import tempfile
import unittest
from pathlib import Path

from PIL import Image

from content_ops.cards import _fit_text, render_wechat_cover, render_xhs_cards
from content_ops.config import save_yaml


BRAND = {
    "name": "Leo的AI生意实验室",
    "colors": {
        "primary": "#2457E6",
        "background": "#F6F2E9",
        "accent": "#FF8A34",
        "text": "#20242C",
    },
}


class CardTests(unittest.TestCase):
    def test_fit_text_avoids_single_character_last_line(self):
        canvas = Image.new("RGB", (1080, 1350), "white")
        from PIL import ImageDraw

        draw = ImageDraw.Draw(canvas)
        _, lines = _fit_text(
            draw,
            "询价，证明用户开始比较方案",
            max_width=900,
            preferred_size=74,
            minimum_size=56,
            max_lines=3,
        )
        self.assertGreater(len(lines[-1]), 1)

    def test_renders_numbered_1080_by_1350_cards(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = Path(tmp)
            (task / "images").mkdir()
            save_yaml(
                task / "manifest.yaml",
                {
                    "content_id": "leo-test",
                    "xhs_cards": [
                        {
                            "layout": "hero_conflict",
                            "eyebrow": "AI生意实验 01",
                            "title": "86条评论，不等于有人付款",
                            "body": "免费领取只能证明兴趣。",
                            "left_metric": "86条评论",
                            "right_metric": "付款数未知",
                        },
                        {
                            "layout": "funnel",
                            "eyebrow": "判断方法",
                            "title": "至少再看三件事",
                            "body": "询价、预付款、持续成交。",
                            "steps": ["互动", "询价", "预付款", "复购"],
                        },
                    ],
                },
            )
            paths = render_xhs_cards(task, BRAND)
            self.assertEqual(
                [path.name for path in paths], ["xhs-01.png", "xhs-02.png"]
            )
            with Image.open(paths[0]) as image:
                self.assertEqual(image.size, (1080, 1350))

    def test_unknown_layout_fails_explicitly(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = Path(tmp)
            (task / "images").mkdir()
            save_yaml(
                task / "manifest.yaml",
                {
                    "content_id": "leo-test",
                    "xhs_cards": [
                        {
                            "layout": "mystery",
                            "eyebrow": "测试",
                            "title": "未知版式",
                            "body": "正文",
                        }
                    ],
                },
            )
            with self.assertRaisesRegex(ValueError, "unknown card layout"):
                render_xhs_cards(task, BRAND)

    def test_renders_wechat_cover_from_first_cover_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = Path(tmp)
            (task / "images").mkdir()
            save_yaml(
                task / "manifest.yaml",
                {
                    "content_id": "leo-test",
                    "packaging": {"covers": ["86条评论 ≠ 有人付款"]},
                },
            )
            path = render_wechat_cover(task, BRAND)
            self.assertEqual(path.name, "wechat-cover.png")
            with Image.open(path) as image:
                self.assertEqual(image.size, (900, 383))

    def test_too_many_title_lines_fail_instead_of_clipping(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = Path(tmp)
            (task / "images").mkdir()
            save_yaml(
                task / "manifest.yaml",
                {
                    "content_id": "leo-test",
                    "xhs_cards": [
                        {
                            "eyebrow": "测试",
                            "title": "这是一段故意写得非常非常非常非常非常非常非常非常非常非常非常非常非常非常长的标题，继续增加内容来确保即使缩小字号也无法在三行安全区域内完整显示",
                            "body": "正文",
                        }
                    ],
                },
            )
            with self.assertRaisesRegex(ValueError, "title is too long"):
                render_xhs_cards(task, BRAND)


if __name__ == "__main__":
    unittest.main()
