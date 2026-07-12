import hashlib
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from content_ops.automation import run_daily
from content_ops.candidates import CandidateBatchStore
from content_ops.config import load_yaml
from content_ops.production import produce_selected_candidate
from content_ops.providers import ModelResult, ModelUsage


TEST_BRAND = {
    "name": "Leo的AI生意实验室",
    "colors": {
        "primary": "#2457E6",
        "background": "#F6F2E9",
        "accent": "#FF8A34",
        "text": "#20242C",
    },
}


class FullPipelineFakeModel:
    def complete_json(self, *, stage, payload, **kwargs):
        if stage == "candidates":
            source_id = payload["sources"][0]["id"]
            data = {
                "candidates": [
                    {
                        "id": "eligible",
                        "title": "评论很多为什么仍不能证明有人付款",
                        "category": "adjacent_broad",
                        "trigger": "评论区集中求资料",
                        "audience": "AI内容创作者",
                        "demand_evidence": ["同一问题反复出现"],
                        "differentiation": "区分互动和付款",
                        "risks": ["不能虚构成交"],
                        "source_ids": [source_id],
                        "scores": {
                            "demand_timeliness": 21,
                            "hook_strength": 17,
                            "consumption_value": 17,
                            "evidence": 12,
                            "differentiation": 8,
                            "account_fit": 8,
                        },
                    }
                ]
            }
        elif stage == "source_pack":
            source = payload["sources"][0]
            data = {
                "sources": [
                    {
                        "id": source["id"],
                        "kind": source["kind"],
                        "path": source["location"],
                    }
                ],
                "claims": [
                    {
                        "text": "用户反复询问自动化成本",
                        "label": "verified",
                        "source_ids": [source["id"]],
                    }
                ],
                "risks": ["不得虚构付款"],
                "markdown": "# 资料与来源\n\n已核验用户反复询问自动化成本。",
            }
        elif stage == "master_draft":
            data = {
                "markdown": "# 内容母稿\n\n评论只能证明钩子，付款才证明商业需求。"
            }
        elif stage == "platform_copy":
            data = {
                "wechat": "# 公众号终稿\n\n这是完整解释需求证据层级的长文内容。",
                "xhs": "# 小红书终稿\n\n评论很多不等于付款，先验证预付款。",
            }
        elif stage == "packaging":
            data = {
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
            }
        else:
            raise AssertionError(f"unexpected stage: {stage}")
        return ModelResult(data, ModelUsage(100, 20), "fake")


class AutomationE2ETests(unittest.TestCase):
    def test_daily_scan_selection_and_production_do_not_modify_raw(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "wiki").mkdir()
            (root / "raw" / "inbox").mkdir(parents=True)
            (root / "content-ops" / "topics").mkdir(parents=True)
            raw = root / "raw" / "inbox" / "evidence.txt"
            raw.write_text("用户反复询问自动化成本", encoding="utf-8")
            before = hashlib.sha256(raw.read_bytes()).hexdigest()
            (root / "wiki" / "evidence.md").write_text(
                "需求证据", encoding="utf-8"
            )
            (root / "content-ops" / "topics" / "backlog.yaml").write_text(
                "topics: []\n", encoding="utf-8"
            )
            model = FullPipelineFakeModel()

            outcome = run_daily(
                root,
                "2026-07-13",
                model,
                datetime(2026, 7, 13, 2, 30, tzinfo=timezone.utc),
            )

            self.assertEqual(outcome.status, "awaiting_topic_selection")
            batch = root / "content-ops" / "candidates" / "2026-07-13.yaml"
            candidate_id = load_yaml(batch)["candidates"][0]["id"]
            CandidateBatchStore(batch).select(candidate_id)
            task = produce_selected_candidate(
                root / "content-ops", batch, model, TEST_BRAND
            )
            self.assertEqual(
                load_yaml(task / "manifest.yaml")["status"],
                "awaiting_review",
            )
            self.assertEqual(hashlib.sha256(raw.read_bytes()).hexdigest(), before)
            second = run_daily(
                root,
                "2026-07-13",
                model,
                datetime(2026, 7, 13, 3, 0, tzinfo=timezone.utc),
            )
            self.assertEqual(second.status, "already_ran")
