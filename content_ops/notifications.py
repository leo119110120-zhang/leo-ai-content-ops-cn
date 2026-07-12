try:
    from winotify import Notification
except ImportError:
    Notification = None


class NullNotifier:
    def send(
        self,
        title: str,
        message: str,
        url: str | None = None,
    ) -> None:
        return None


class WindowsToastNotifier:
    def send(
        self,
        title: str,
        message: str,
        url: str | None = None,
    ) -> None:
        if Notification is None:
            raise RuntimeError(
                "winotify is not installed; install requirements-content-ops.txt"
            )
        toast = Notification(
            app_id="Leo AI 内容运营",
            title=title,
            msg=message,
            duration="short",
        )
        if url:
            toast.add_actions(label="打开", launch=url)
        toast.show()
