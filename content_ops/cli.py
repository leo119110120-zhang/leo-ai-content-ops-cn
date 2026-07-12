from argparse import ArgumentParser
from datetime import date, datetime, timezone
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import yaml

from content_ops.cards import render_wechat_cover, render_xhs_cards
from content_ops.automation import run_daily
from content_ops.candidate_server import build_candidate_server
from content_ops.config import load_yaml
from content_ops.models import ContentStatus
from content_ops.notifications import WindowsToastNotifier
from content_ops.packaging import export_publish_package
from content_ops.production import produce_selected_candidate
from content_ops.providers.deepseek import DeepSeekClient
from content_ops.quality import run_quality_checks, write_quality_report
from content_ops.review import render_review
from content_ops.scoring import explain_gate, score_topic
from content_ops.server import serve
from content_ops.storage import create_task, transition


def _parser() -> ArgumentParser:
    parser = ArgumentParser(prog="content-ops")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("score", "create"):
        command = sub.add_parser(name)
        command.add_argument("topic")
    for name in (
        "transition",
        "qa",
        "cards",
        "review",
        "serve",
        "package",
    ):
        command = sub.add_parser(name)
        command.add_argument("task")
    sub.choices["create"].add_argument(
        "--date", default=date.today().isoformat()
    )
    sub.choices["transition"].add_argument(
        "target", choices=[value.value for value in ContentStatus]
    )
    sub.choices["transition"].add_argument("--note", default="")
    sub.choices["serve"].add_argument("--port", type=int, default=8765)
    daily = sub.add_parser("daily")
    daily.add_argument("--root", default=".")
    daily.add_argument("--date", default=date.today().isoformat())
    candidates = sub.add_parser("serve-candidates")
    candidates.add_argument("batch")
    candidates.add_argument("--root", default=".")
    candidates.add_argument("--port", type=int, default=8766)
    produce = sub.add_parser("produce-selected")
    produce.add_argument("batch")
    produce.add_argument("--root", default=".")
    return parser


def _deepseek_client(root: Path) -> DeepSeekClient:
    path = root / "content-ops" / "config" / "automation.yaml"
    config = load_yaml(path).get("deepseek", {}) if path.exists() else {}
    return DeepSeekClient.from_env(
        base_url=config.get("base_url", "https://api.deepseek.com"),
        model=config.get("model", "deepseek-v4-flash"),
        timeout=int(config.get("timeout_seconds", 90)),
        max_retries=int(config.get("max_retries", 2)),
    )


def launch_hidden(args: list[str], root: Path) -> subprocess.Popen:
    flags = 0
    if os.name == "nt":
        flags = (
            subprocess.CREATE_NO_WINDOW
            | subprocess.DETACHED_PROCESS
            | subprocess.CREATE_NEW_PROCESS_GROUP
        )
    return subprocess.Popen(
        [sys.executable, "-m", "content_ops.cli", *args],
        cwd=root,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        creationflags=flags,
    )


def wait_for_loopback(port: int, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def _run_daily_command(args) -> int:
    root = Path(args.root).resolve()
    outcome = run_daily(
        root,
        args.date,
        _deepseek_client(root),
        datetime.now(timezone.utc),
    )
    print(f"{outcome.status}: {outcome.message}")
    if outcome.status not in {
        "awaiting_topic_selection",
        "waiting_for_human",
    }:
        return 0
    if outcome.artifact is None:
        print("等待人工处理，但没有可自动打开的页面")
        return 0
    if outcome.artifact.name == "review.html":
        launch_hidden(
            ["serve", str(outcome.artifact.parent), "--port", "8765"],
            root,
        )
        if not wait_for_loopback(8765):
            print(f"review server failed; open {outcome.artifact}", file=sys.stderr)
            return 1
        WindowsToastNotifier().send(
            "Leo内容终稿等待审核",
            "点击继续审核未处理的内容",
            "http://127.0.0.1:8765/review.html",
        )
        return 0
    if outcome.artifact.parent.name != "candidates":
        print(f"请人工检查：{outcome.artifact}")
        return 0
    batch = outcome.artifact.with_suffix(".yaml")
    launch_hidden(
        [
            "serve-candidates",
            str(batch),
            "--root",
            str(root),
            "--port",
            "8766",
        ],
        root,
    )
    if not wait_for_loopback(8766):
        print(f"candidate server failed; open {outcome.artifact}", file=sys.stderr)
        return 1
    WindowsToastNotifier().send(
        "Leo内容候选已就绪",
        "打开页面，从合格选题中选择一个",
        "http://127.0.0.1:8766/",
    )
    return 0


def _serve_candidates_command(args) -> int:
    root = Path(args.root).resolve()
    batch = Path(args.batch).resolve()
    holder = {}

    def on_selected(batch_path: Path, candidate_id: str) -> None:
        launch_hidden(
            ["produce-selected", str(batch_path), "--root", str(root)],
            root,
        )
        holder["server"].shutdown()

    server = build_candidate_server(batch, args.port, on_selected)
    holder["server"] = server
    print(f"Candidate center: http://127.0.0.1:{server.server_address[1]}/")
    try:
        server.serve_forever()
    finally:
        server.server_close()
    return 0


def _produce_selected_command(args) -> int:
    root = Path(args.root).resolve()
    task = produce_selected_candidate(
        root / "content-ops",
        Path(args.batch).resolve(),
        _deepseek_client(root),
        load_yaml(root / "content-ops" / "config" / "brand.yaml"),
    )
    status = load_yaml(task / "manifest.yaml")["status"]
    if status == ContentStatus.AWAITING_REVIEW.value:
        launch_hidden(["serve", str(task), "--port", "8765"], root)
        if not wait_for_loopback(8765):
            print(f"review server failed; open {task / 'review.html'}", file=sys.stderr)
            return 1
        WindowsToastNotifier().send(
            "Leo内容终稿等待审核",
            "公众号、小红书和图片已经生成",
            "http://127.0.0.1:8765/review.html",
        )
        return 0
    WindowsToastNotifier().send(
        "Leo内容自动质检未通过",
        f"请检查本地任务：{task}",
    )
    return 1


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command in {"score", "create"}:
        topic = load_yaml(Path(args.topic))
    if args.command == "score":
        score = score_topic(topic)
        print(
            yaml.safe_dump(
                {
                    "total": score.total,
                    "eligible": score.eligible,
                    "reasons": explain_gate(score),
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            end="",
        )
    elif args.command == "create":
        print(create_task(Path("content-ops"), topic, args.date))
    elif args.command == "transition":
        print(
            transition(
                Path(args.task), ContentStatus(args.target), args.note
            )["status"]
        )
    elif args.command == "qa":
        report = run_quality_checks(Path(args.task))
        write_quality_report(Path(args.task), report)
        print("PASS" if report.passed else "FAIL")
        return 0 if report.passed else 1
    elif args.command == "cards":
        brand = load_yaml(Path("content-ops/config/brand.yaml"))
        print(render_wechat_cover(Path(args.task), brand))
        print(*render_xhs_cards(Path(args.task), brand), sep="\n")
    elif args.command == "review":
        print(render_review(Path(args.task), Path(args.task) / "review.html"))
    elif args.command == "serve":
        serve(Path(args.task), args.port)
    elif args.command == "package":
        print(
            export_publish_package(
                Path(args.task), Path("content-ops/ready-to-publish")
            )
        )
    elif args.command == "daily":
        return _run_daily_command(args)
    elif args.command == "serve-candidates":
        return _serve_candidates_command(args)
    elif args.command == "produce-selected":
        return _produce_selected_command(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
