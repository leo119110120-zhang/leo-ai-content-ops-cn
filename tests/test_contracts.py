import unittest

from content_ops.contracts import (
    require_exact_fields,
    require_mapping,
    require_nonempty_string,
    require_string_list,
)


class ContractTests(unittest.TestCase):
    def test_mapping_rejects_non_mapping(self):
        with self.assertRaisesRegex(ValueError, "payload must be an object"):
            require_mapping([], "payload")

    def test_exact_fields_rejects_missing_and_unexpected_fields(self):
        with self.assertRaisesRegex(
            ValueError,
            r"value has invalid fields: missing=b; unexpected=c",
        ):
            require_exact_fields({"a": 1, "c": 2}, {"a", "b"}, "value")

    def test_nonempty_string_rejects_blank_value(self):
        with self.assertRaisesRegex(ValueError, "title must be a non-empty string"):
            require_nonempty_string("  ", "title")

    def test_string_is_not_accepted_as_string_list(self):
        with self.assertRaisesRegex(
            ValueError,
            "candidate.demand_evidence must be a list of strings",
        ):
            require_string_list(
                "公开讨论中反复出现",
                "candidate.demand_evidence",
            )

    def test_string_list_rejects_blank_items_with_path(self):
        with self.assertRaisesRegex(
            ValueError,
            r"risks\[1\] must be a non-empty string",
        ):
            require_string_list(["有效", ""], "risks")

    def test_string_list_can_explicitly_allow_empty(self):
        self.assertEqual(
            require_string_list([], "risks", allow_empty=True),
            [],
        )


if __name__ == "__main__":
    unittest.main()
