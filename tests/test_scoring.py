import unittest

from content_ops.scoring import explain_gate, score_topic


class ScoringTests(unittest.TestCase):
    def test_eligible_topic_passes(self):
        topic = {
            "scores": {
                "demand_timeliness": 21,
                "hook_strength": 17,
                "consumption_value": 17,
                "evidence": 12,
                "differentiation": 8,
                "account_fit": 8,
            }
        }
        score = score_topic(topic)
        self.assertEqual(score.total, 83)
        self.assertTrue(score.eligible)
        self.assertEqual(explain_gate(score), [])

    def test_creator_interest_without_user_demand_fails(self):
        topic = {
            "scores": {
                "demand_timeliness": 12,
                "hook_strength": 20,
                "consumption_value": 20,
                "evidence": 15,
                "differentiation": 10,
                "account_fit": 10,
            }
        }
        score = score_topic(topic)
        self.assertEqual(score.total, 87)
        self.assertFalse(score.eligible)
        self.assertIn(
            "demand_timeliness must be at least 15", explain_gate(score)
        )

    def test_out_of_range_score_fails(self):
        with self.assertRaisesRegex(ValueError, "hook_strength"):
            score_topic(
                {
                    "scores": {
                        "demand_timeliness": 20,
                        "hook_strength": 21,
                        "consumption_value": 10,
                        "evidence": 10,
                        "differentiation": 5,
                        "account_fit": 5,
                    }
                }
            )


if __name__ == "__main__":
    unittest.main()
