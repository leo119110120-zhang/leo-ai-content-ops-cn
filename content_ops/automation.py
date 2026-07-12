from dataclasses import asdict
from datetime import datetime, timedelta
import json
from pathlib import Path

from content_ops.candidate_review import render_candidates
from content_ops.candidates import CandidateBatchStore, generate_candidate_batch
from content_ops.config import load_yaml, save_yaml
from content_ops.models import DailyOutcome
from content_ops.source_collector import collect_sources


ACTIVE_CONTENT = {
    "researching",
    "drafting",
    "qa_failed",
    "qa_passed",
    "awaiting_review",
    "revision_requested",
}


def _pending_artifact(root: Path) -> tuple[str, Path | None] | None:
    drafts = root / "content-ops" / "drafts"
    for path in sorted(drafts.glob("*/manifest.yaml"), reverse=True):
        try:
            status = load_yaml(path).get("status")
        except Exception:
            return "malformed", path
        if status in ACTIVE_CONTENT:
            review = path.parent / "review.html"
            return status, review if review.exists() else path
    candidates = root / "content-ops" / "candidates"
    for path in sorted(candidates.glob("*.yaml"), reverse=True):
        try:
            status = load_yaml(path).get("status")
        except Exception:
            return "malformed", path
        if status == "awaiting_topic_selection":
            page = render_candidates(path, path.with_suffix(".html"))
            return status, page
    return None


def _acquire_lease(
    lock: Path,
    now: datetime,
    stale_after: timedelta = timedelta(hours=2),
) -> bool:
    if lock.exists():
        try:
            started_at = datetime.fromisoformat(load_yaml(lock)["started_at"])
            age = now - started_at
        except Exception:
            modified = datetime.fromtimestamp(
                lock.stat().st_mtime,
                tz=now.tzinfo,
            )
            age = now - modified
        if age <= stale_after:
            return False
        lock.unlink(missing_ok=True)
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        with lock.open("x", encoding="utf-8") as handle:
            json.dump({"started_at": now.isoformat()}, handle)
        return True
    except FileExistsError:
        return False


def _restore_cache(cache_path: Path, previous: bytes | None) -> None:
    if previous is None:
        cache_path.unlink(missing_ok=True)
    else:
        cache_path.write_bytes(previous)


def run_daily(
    root: Path,
    run_date: str,
    model,
    now: datetime,
) -> DailyOutcome:
    root = root.resolve()
    state = root / "content-ops" / "state"
    state.mkdir(parents=True, exist_ok=True)
    done = state / f"daily-{run_date}.done"
    if done.exists():
        return DailyOutcome("already_ran", "today's scan already completed")
    pending = _pending_artifact(root)
    if pending:
        pending_status, artifact = pending
        return DailyOutcome(
            "waiting_for_human",
            f"pending human action: {pending_status}",
            artifact,
        )

    lock = state / f"daily-{run_date}.lock"
    if not _acquire_lease(lock, now):
        return DailyOutcome("already_running", "scan already running")

    cache_path = state / "source-cache.yaml"
    previous_cache = cache_path.read_bytes() if cache_path.exists() else None
    logs = root / "content-ops" / "logs"
    try:
        records = collect_sources(root, state, now)
        batch = generate_candidate_batch(
            run_date,
            [asdict(record) for record in records],
            model,
        )
        candidates = root / "content-ops" / "candidates"
        candidates.mkdir(parents=True, exist_ok=True)
        batch_path = candidates / f"{run_date}.yaml"
        CandidateBatchStore(batch_path).create(batch)
        page = render_candidates(
            batch_path,
            candidates / f"{run_date}.html",
        )
        save_yaml(
            done,
            {
                "status": batch["status"],
                "completed_at": now.isoformat(),
                "artifact": str(page),
            },
        )
        save_yaml(
            logs / f"daily-{run_date}.yaml",
            {
                "status": batch["status"],
                "completed_at": now.isoformat(),
                "source_count": len(records),
                "candidate_count": len(batch["candidates"]),
            },
        )
        return DailyOutcome(batch["status"], batch["status"], page)
    except Exception as error:
        _restore_cache(cache_path, previous_cache)
        save_yaml(
            logs / f"daily-{run_date}.yaml",
            {
                "status": "failed",
                "failed_at": now.isoformat(),
                "error_type": type(error).__name__,
            },
        )
        raise
    finally:
        lock.unlink(missing_ok=True)
