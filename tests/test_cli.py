import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from content_ops.config import save_yaml
from content_ops.models import DailyOutcome


class CLITests(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "content_ops.cli", *args],
            cwd=Path(__file__).parents[1],
            text=True,
            capture_output=True,
            encoding="utf-8",
            check=False,
        )

    def test_help_lists_all_commands(self):
        result = self.run_cli("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        for command in (
            "score",
            "create",
            "transition",
            "qa",
            "cards",
            "review",
            "serve",
            "package",
            "daily",
            "serve-candidates",
            "produce-selected",
        ):
            self.assertIn(command, result.stdout)

    def test_score_command_reports_eligible_topic(self):
        with tempfile.TemporaryDirectory() as tmp:
            topic = Path(tmp) / "topic.yaml"
            save_yaml(
                topic,
                {
                    "scores": {
                        "demand_timeliness": 21,
                        "hook_strength": 17,
                        "consumption_value": 17,
                        "evidence": 12,
                        "differentiation": 8,
                        "account_fit": 8,
                    }
                },
            )
            result = self.run_cli("score", str(topic))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("eligible: true", result.stdout.lower())
            self.assertIn("total: 83", result.stdout.lower())

    @patch("content_ops.cli._deepseek_client")
    @patch("content_ops.cli.run_daily")
    @patch("content_ops.cli.launch_hidden")
    @patch("content_ops.cli.wait_for_loopback")
    @patch("content_ops.cli.WindowsToastNotifier")
    def test_daily_notifies_only_after_candidate_server_is_ready(
        self,
        notifier,
        wait_for_loopback,
        launch_hidden,
        run_daily,
        deepseek_client,
    ):
        from content_ops.cli import main

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact = root / "content-ops" / "candidates" / "2026-07-13.html"
            run_daily.return_value = DailyOutcome(
                "awaiting_topic_selection",
                "ready",
                artifact,
            )
            events = []
            launch_hidden.side_effect = lambda *args: events.append("launch")
            wait_for_loopback.side_effect = lambda *args: events.append("wait") or True
            notifier.return_value.send.side_effect = (
                lambda *args: events.append("notify")
            )

            result = main(
                ["daily", "--root", str(root), "--date", "2026-07-13"]
            )

            self.assertEqual(result, 0)
            self.assertEqual(events, ["launch", "wait", "notify"])
            launched = " ".join(launch_hidden.call_args.args[0])
            self.assertIn("serve-candidates", launched)
            self.assertNotIn("DEEPSEEK_API_KEY", launched)

    @patch("content_ops.cli._deepseek_client")
    @patch("content_ops.cli.run_daily")
    @patch("content_ops.cli.launch_hidden")
    @patch("content_ops.cli.wait_for_loopback", return_value=False)
    @patch("content_ops.cli.WindowsToastNotifier")
    def test_daily_does_not_send_dead_candidate_link(
        self,
        notifier,
        wait_for_loopback,
        launch_hidden,
        run_daily,
        deepseek_client,
    ):
        from content_ops.cli import main

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact = root / "content-ops" / "candidates" / "2026-07-13.html"
            run_daily.return_value = DailyOutcome(
                "awaiting_topic_selection",
                "ready",
                artifact,
            )

            result = main(
                ["daily", "--root", str(root), "--date", "2026-07-13"]
            )

            self.assertEqual(result, 1)
            notifier.return_value.send.assert_not_called()

    @patch("content_ops.cli._deepseek_client")
    @patch("content_ops.cli.run_daily")
    @patch("content_ops.cli.launch_hidden")
    @patch("content_ops.cli.wait_for_loopback", return_value=True)
    @patch("content_ops.cli.WindowsToastNotifier")
    def test_daily_restarts_server_for_pending_candidate_after_reboot(
        self,
        notifier,
        wait_for_loopback,
        launch_hidden,
        run_daily,
        deepseek_client,
    ):
        from content_ops.cli import main

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact = root / "content-ops" / "candidates" / "2026-07-12.html"
            run_daily.return_value = DailyOutcome(
                "waiting_for_human",
                "pending human action: awaiting_topic_selection",
                artifact,
            )

            result = main(
                ["daily", "--root", str(root), "--date", "2026-07-13"]
            )

            self.assertEqual(result, 0)
            self.assertIn("serve-candidates", launch_hidden.call_args.args[0])
            notifier.return_value.send.assert_called_once()


if __name__ == "__main__":
    unittest.main()
