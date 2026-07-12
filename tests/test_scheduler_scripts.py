import unittest
from pathlib import Path


class SchedulerScriptTests(unittest.TestCase):
    def test_installer_has_exact_weekday_time_and_recovery(self):
        text = Path("scripts/install-content-ops-task.ps1").read_text(
            encoding="utf-8"
        )
        self.assertIn("LeoContentOpsDaily", text)
        self.assertIn("-At '10:30'", text)
        self.assertIn(
            "Monday,Tuesday,Wednesday,Thursday,Friday",
            text.replace(" ", ""),
        )
        self.assertIn("-StartWhenAvailable", text)
        self.assertIn("-m content_ops.cli daily", text)
        self.assertNotIn("DEEPSEEK_API_KEY=", text)

    def test_uninstaller_removes_only_named_task_without_prompt(self):
        text = Path("scripts/uninstall-content-ops-task.ps1").read_text(
            encoding="utf-8"
        )
        self.assertIn("LeoContentOpsDaily", text)
        self.assertIn("Unregister-ScheduledTask", text)
        self.assertIn("-Confirm:$false", text)
