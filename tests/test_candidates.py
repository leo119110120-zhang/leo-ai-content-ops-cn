import tempfile
import unittest
from pathlib import Path

from content_ops.candidates import CandidateBatchStore, generate_candidate_batch
from content_ops.prompts import CANDIDATE_SYSTEM
from content_ops.providers import ModelResult, ModelUsage


def candidate(candidate_id: str, **overrides) -> dict:
    value = {
        "id": candidate_id,
        "title": "评论很多为什么仍不能证明有人付款",
        "category": "adjacent_broad",
        "trigger": "评论区集中求资料",
        "audience": "AI内容创作者",
        "demand_evidence": ["同一问题反复出现"],
        "differentiation": "区分互动和付款",
        "risks": ["不能虚构成交"],
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
    value.update(overrides)
    return value


class FakeModel:
    def complete_json(self, **kwargs):
        return ModelResult(
            {
                "candidates": [
                    candidate("eligible"),
                    candidate(
                        "creator-only",
                        title="我想聊的AI趋势",
                        trigger="作者想写",
                        demand_evidence=[],
                        differentiation="无",
                        scores={
                            "demand_timeliness": 12,
                            "hook_strength": 20,
                            "consumption_value": 20,
                            "evidence": 15,
                            "differentiation": 10,
                            "account_fit": 10,
                        },
                    ),
                ]
            },
            ModelUsage(100, 40),
            "fake",
        )


class ResponseModel:
    def __init__(self, data):
        self.data = data

    def complete_json(self, **kwargs):
        return ModelResult(
            self.data,
            ModelUsage(10, 5),
            "fake",
        )


class CandidateTests(unittest.TestCase):
    def test_candidate_prompt_declares_exact_score_keys_and_ranges(self):
        expected = {
            "demand_timeliness": 25,
            "hook_strength": 20,
            "consumption_value": 20,
            "evidence": 15,
            "differentiation": 10,
            "account_fit": 10,
        }
        for key, maximum in expected.items():
            self.assertIn(f'"{key}": 0-{maximum}', CANDIDATE_SYSTEM)
        self.assertIn("禁止使用0到1的小数", CANDIDATE_SYSTEM)

    def test_candidate_prompt_declares_list_field_types(self):
        self.assertIn("demand_evidence、risks、source_ids必须是JSON字符串数组", CANDIDATE_SYSTEM)

    def test_candidates_must_be_a_list(self):
        with self.assertRaisesRegex(
            ValueError,
            "candidate_response.candidates must be a list",
        ):
            generate_candidate_batch(
                "2026-07-13",
                [{"id": "s1", "content": "真实来源"}],
                ResponseModel({"candidates": "不是数组"}),
            )

    def test_candidate_evidence_string_fails_clearly(self):
        with self.assertRaisesRegex(
            ValueError,
            r"candidate\[0\]\.demand_evidence must be a list of strings",
        ):
            generate_candidate_batch(
                "2026-07-13",
                [{"id": "s1", "content": "真实来源"}],
                ResponseModel(
                    {
                        "candidates": [
                            candidate(
                                "bad-evidence",
                                demand_evidence="公开讨论中反复出现",
                            )
                        ]
                    }
                ),
            )

    def test_candidate_risks_string_fails_clearly(self):
        with self.assertRaisesRegex(
            ValueError,
            r"candidate\[0\]\.risks must be a list of strings",
        ):
            generate_candidate_batch(
                "2026-07-13",
                [{"id": "s1", "content": "真实来源"}],
                ResponseModel(
                    {"candidates": [candidate("bad-risks", risks="风险文本")]}
                ),
            )

    def test_duplicate_candidate_ids_fail_clearly(self):
        with self.assertRaisesRegex(ValueError, "candidate ids must be unique"):
            generate_candidate_batch(
                "2026-07-13",
                [{"id": "s1", "content": "真实来源"}],
                ResponseModel(
                    {"candidates": [candidate("same"), candidate("same")]}
                ),
            )

    def test_alternative_float_score_schema_fails_clearly(self):
        class FloatScoreModel:
            def complete_json(self, **kwargs):
                item = candidate(
                    "invalid-scores",
                    scores={
                        "demand": 0.9,
                        "feasibility": 0.8,
                        "uniqueness": 0.7,
                        "scalability": 0.6,
                        "timeliness": 0.5,
                        "risk_mitigation": 0.4,
                    },
                )
                return ModelResult(
                    {"candidates": [item]},
                    ModelUsage(10, 5),
                    "fake",
                )

        with self.assertRaisesRegex(
            ValueError,
            r"candidate\[0\]\.scores has invalid fields",
        ):
            generate_candidate_batch(
                "2026-07-13",
                [{"id": "s1", "content": "真实来源"}],
                FloatScoreModel(),
            )

    def test_ineligible_items_are_not_used_to_fill_three_slots(self):
        sources = [{"id": "s1", "content": "真实来源"}]
        batch = generate_candidate_batch("2026-07-13", sources, FakeModel())
        self.assertEqual(
            [item["id"] for item in batch["candidates"]], ["eligible"]
        )
        self.assertEqual(batch["status"], "awaiting_topic_selection")
        self.assertEqual(batch["sources"], sources)

    def test_candidate_referencing_unknown_source_is_filtered(self):
        class UnknownSourceModel:
            def complete_json(self, **kwargs):
                return ModelResult(
                    {
                        "candidates": [
                            candidate("invented", source_ids=["missing"])
                        ]
                    },
                    ModelUsage(10, 5),
                    "fake",
                )

        batch = generate_candidate_batch(
            "2026-07-13",
            [{"id": "s1", "content": "真实来源"}],
            UnknownSourceModel(),
        )
        self.assertEqual(batch["status"], "no_candidates")
        self.assertEqual(batch["candidates"], [])

    def test_selection_is_idempotent_and_rejects_second_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "batch.yaml"
            store = CandidateBatchStore(path)
            store.create(
                {
                    "run_date": "2026-07-13",
                    "status": "awaiting_topic_selection",
                    "candidates": [{"id": "a"}, {"id": "b"}],
                }
            )
            first = store.select("a")
            second = store.select("a")
            self.assertEqual(first, second)
            with self.assertRaisesRegex(ValueError, "already selected"):
                store.select("b")

    def test_at_most_three_eligible_candidates_are_kept(self):
        class FourCandidateModel:
            def complete_json(self, **kwargs):
                return ModelResult(
                    {"candidates": [candidate(str(index)) for index in range(4)]},
                    ModelUsage(100, 40),
                    "fake",
                )

        batch = generate_candidate_batch(
            "2026-07-13",
            [{"id": "s1", "content": "真实来源"}],
            FourCandidateModel(),
        )
        self.assertEqual(len(batch["candidates"]), 3)
