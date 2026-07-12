import tempfile
import unittest
from pathlib import Path

from content_ops.config import ConfigError, load_yaml, save_yaml


class ConfigTests(unittest.TestCase):
    def test_round_trip_yaml(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "value.yaml"
            save_yaml(path, {"name": "Leo的AI生意实验室", "version": 1})
            self.assertEqual(load_yaml(path)["version"], 1)

    def test_missing_required_brand_keys_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "brand.yaml"
            save_yaml(path, {"name": "Leo"})
            with self.assertRaisesRegex(ConfigError, "tagline"):
                load_yaml(path, required={"name", "tagline", "colors"})


if __name__ == "__main__":
    unittest.main()
