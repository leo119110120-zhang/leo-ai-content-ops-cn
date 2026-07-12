import unittest
from unittest.mock import patch

from content_ops.notifications import WindowsToastNotifier


class NotificationTests(unittest.TestCase):
    @patch("content_ops.notifications.Notification")
    def test_windows_toast_has_open_action(self, notification):
        instance = notification.return_value

        WindowsToastNotifier().send(
            "候选已就绪",
            "3个候选",
            "http://127.0.0.1:8766/",
        )

        instance.add_actions.assert_called_once_with(
            label="打开",
            launch="http://127.0.0.1:8766/",
        )
        instance.show.assert_called_once()
