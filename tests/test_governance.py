import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class GovernanceTests(unittest.TestCase):
    def test_editorial_policy_keeps_selection_and_evidence_rules(self):
        policy = load_yaml(
            ROOT / "content-ops" / "config" / "editorial-policy.yaml"
        )

        self.assertEqual(policy["selection"]["minimum_total_score"], 75)
        self.assertEqual(
            policy["selection"]["minimum_demand_timeliness"], 15
        )
        self.assertEqual(policy["selection"]["maximum_candidates"], 3)
        self.assertTrue(policy["selection"]["traceable_source_required"])
        self.assertEqual(
            policy["evidence_ladder"][-3:],
            ["payment", "repeat_purchase", "referral"],
        )

    def test_editorial_policy_keeps_content_mix_and_human_gates(self):
        policy = load_yaml(
            ROOT / "content-ops" / "config" / "editorial-policy.yaml"
        )

        self.assertEqual(sum(policy["cold_start_mix"].values()), 100)
        self.assertEqual(policy["cold_start_mix"]["adjacent_broad"], 60)
        self.assertEqual(
            policy["human_gates"],
            ["topic_selection", "final_review", "platform_publish"],
        )
        self.assertFalse(policy["automation"]["automatic_publish"])
        self.assertEqual(policy["automation"]["maximum_model_retries"], 2)

    def test_state_example_uses_unknown_instead_of_assuming_accounts(self):
        state = load_yaml(
            ROOT / "content-ops" / "config" / "project-state.example.yaml"
        )

        self.assertEqual(state["accounts"]["wechat"], "unknown")
        self.assertEqual(state["accounts"]["xiaohongshu"], "unknown")
        self.assertIn("current_stage", state)
        self.assertIn("known_blockers", state)
        self.assertIn("next_actions", state)

    def test_agents_file_requires_startup_and_shutdown_protocols(self):
        text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

        for value in (
            "content-ops/state/project-state.yaml",
            "content-ops/config/editorial-policy.yaml",
            "不得自动发布",
            "不得修改 `raw/`",
            "必须报告冲突",
            "完成前必须验证",
        ):
            self.assertIn(value, text)

    def test_decisions_and_release_checklist_are_present(self):
        decisions = (ROOT / "docs" / "DECISIONS.md").read_text(
            encoding="utf-8"
        )
        checklist = (
            ROOT / "docs" / "content-release-checklist.md"
        ).read_text(encoding="utf-8")

        self.assertIn("不做纯 AI 资讯号", decisions)
        self.assertIn("真实付款才算商业验证", decisions)
        self.assertIn("来源与事实", checklist)
        self.assertIn("人工发布", checklist)


if __name__ == "__main__":
    unittest.main()
