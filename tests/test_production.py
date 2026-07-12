import tempfile
import unittest
from pathlib import Path

from content_ops.config import load_yaml, save_yaml
from content_ops.production import produce_selected_candidate
from content_ops.providers import ModelResult, ModelUsage


class FakeProductionModel:
    def complete_json(self, *, stage, **kwargs):
        payloads = {
            "source_pack": {
                "sources": [
                    {"id": "s1", "kind": "wiki", "path": "wiki/test.md"}
                ],
                "claims": [
                    {
                        "text": "用户反复询问",
                        "label": "verified",
                        "source_ids": ["s1"],
                    }
                ],
                "risks": ["不得虚构付款"],
                "markdown": "# 资料与来源\n\n已核验用户反复询问这一事实。",
            },
            "master_draft": {
                "markdown": "# 内容母稿\n\n评论只能证明钩子，付款才证明商业需求。"
            },
            "platform_copy": {
                "wechat": "# 公众号终稿\n\n这是完整解释需求证据层级的长文内容。",
                "xhs": "# 小红书终稿\n\n评论很多不等于付款，先看预付款。",
            },
            "packaging": {
                "titles": ["标题一", "标题二", "标题三", "标题四", "标题五"],
                "covers": ["评论不等于付款", "先验证真需求", "别被互动骗了"],
                "openings": ["评论很多，为什么还不能做？", "先别急着做资料包。"],
                "reader_payoff": "学会判断需求证据",
                "discussion_question": "你先看评论还是付款？",
                "xhs_cards": [
                    {
                        "layout": "standard",
                        "eyebrow": "需求验证",
                        "title": "评论不等于付款",
                        "body": "先看预付款和复购。",
                    }
                ],
            },
        }
        return ModelResult(payloads[stage], ModelUsage(100, 20), "fake")


def selected_batch(root: Path) -> Path:
    batch = root / "batch.yaml"
    save_yaml(
        batch,
        {
            "run_date": "2026-07-13",
            "status": "selected",
            "selected_id": "a",
            "sources": [
                {
                    "id": "s1",
                    "kind": "wiki",
                    "title": "需求证据",
                    "content": "用户反复询问",
                    "location": "wiki/test.md",
                    "retrieved_at": "2026-07-13",
                    "sha256": "abc",
                }
            ],
            "candidates": [
                {
                    "id": "a",
                    "title": "评论不等于付款",
                    "category": "adjacent_broad",
                    "trigger": "评论集中求资料",
                    "audience": "AI创作者",
                    "demand_evidence": ["重复提问"],
                    "differentiation": "区分互动和付款",
                    "source_ids": ["s1"],
                    "scores": {
                        "demand_timeliness": 21,
                        "hook_strength": 17,
                        "consumption_value": 17,
                        "evidence": 12,
                        "differentiation": 8,
                        "account_fit": 8,
                    },
                }
            ],
        },
    )
    return batch


TEST_BRAND = {
    "name": "Leo的AI生意实验室",
    "colors": {
        "primary": "#2457E6",
        "background": "#F6F2E9",
        "accent": "#FF8A34",
        "text": "#20242C",
    },
}


class ProductionTests(unittest.TestCase):
    def test_selected_candidate_reaches_awaiting_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch = selected_batch(root)

            task = produce_selected_candidate(
                root / "content-ops",
                batch,
                FakeProductionModel(),
                TEST_BRAND,
            )

            manifest = load_yaml(task / "manifest.yaml")
            self.assertEqual(manifest["status"], "awaiting_review")
            self.assertTrue((task / "review.html").exists())
            self.assertTrue((task / "images" / "wechat-cover.png").exists())
            self.assertTrue((task / "images" / "xhs-01.png").exists())
            self.assertEqual(
                set(manifest["model_usage"]),
                {"source_pack", "master_draft", "platform_copy", "packaging"},
            )

    def test_source_pack_cannot_replace_snapshot_with_unknown_source(self):
        class InventingModel(FakeProductionModel):
            def complete_json(self, *, stage, **kwargs):
                result = super().complete_json(stage=stage, **kwargs)
                if stage == "source_pack":
                    result.data["sources"][0]["id"] = "invented"
                return result

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(ValueError, "unknown sources"):
                produce_selected_candidate(
                    root / "content-ops",
                    selected_batch(root),
                    InventingModel(),
                    TEST_BRAND,
                )
            self.assertFalse((root / "content-ops" / "drafts").exists())

    def test_source_pack_rejects_string_risks_before_task_creation(self):
        class StringRisksModel(FakeProductionModel):
            def complete_json(self, *, stage, **kwargs):
                result = super().complete_json(stage=stage, **kwargs)
                if stage == "source_pack":
                    result.data["risks"] = "不得虚构付款"
                return result

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(
                ValueError,
                "source_pack.risks must be a list of strings",
            ):
                produce_selected_candidate(
                    root / "content-ops",
                    selected_batch(root),
                    StringRisksModel(),
                    TEST_BRAND,
                )
            self.assertFalse((root / "content-ops" / "drafts").exists())

    def test_platform_copy_rejects_blank_wechat_text(self):
        class BlankWechatModel(FakeProductionModel):
            def complete_json(self, *, stage, **kwargs):
                result = super().complete_json(stage=stage, **kwargs)
                if stage == "platform_copy":
                    result.data["wechat"] = "  "
                return result

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(
                ValueError,
                "platform_copy.wechat must be a non-empty string",
            ):
                produce_selected_candidate(
                    root / "content-ops",
                    selected_batch(root),
                    BlankWechatModel(),
                    TEST_BRAND,
                )

    def test_packaging_requires_exact_title_count(self):
        class ShortTitlesModel(FakeProductionModel):
            def complete_json(self, *, stage, **kwargs):
                result = super().complete_json(stage=stage, **kwargs)
                if stage == "packaging":
                    result.data["titles"] = ["只有一个标题"]
                return result

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(
                ValueError,
                "packaging.titles must contain exactly 5 items",
            ):
                produce_selected_candidate(
                    root / "content-ops",
                    selected_batch(root),
                    ShortTitlesModel(),
                    TEST_BRAND,
                )
