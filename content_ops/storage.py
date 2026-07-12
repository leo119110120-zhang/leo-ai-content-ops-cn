from datetime import datetime, timezone
from pathlib import Path
import re

from content_ops.config import load_yaml, save_yaml
from content_ops.models import ContentStatus
from content_ops.scoring import explain_gate, score_topic


TRANSITIONS = {
    ContentStatus.RESEARCHING: {
        ContentStatus.DRAFTING,
        ContentStatus.REJECTED,
    },
    ContentStatus.DRAFTING: {
        ContentStatus.QA_FAILED,
        ContentStatus.QA_PASSED,
    },
    ContentStatus.QA_FAILED: {
        ContentStatus.DRAFTING,
        ContentStatus.REJECTED,
    },
    ContentStatus.QA_PASSED: {ContentStatus.AWAITING_REVIEW},
    ContentStatus.AWAITING_REVIEW: {
        ContentStatus.APPROVED,
        ContentStatus.REVISION_REQUESTED,
        ContentStatus.REJECTED,
    },
    ContentStatus.REVISION_REQUESTED: {ContentStatus.DRAFTING},
    ContentStatus.APPROVED: {ContentStatus.READY_TO_PUBLISH},
    ContentStatus.READY_TO_PUBLISH: {ContentStatus.PUBLISHED},
    ContentStatus.PUBLISHED: {ContentStatus.MEASURED},
    ContentStatus.MEASURED: {ContentStatus.LEARNED},
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9-]+", "-", value).strip("-").lower()
    return cleaned or "content"


def create_task(root: Path, topic: dict, run_date: str) -> Path:
    score = score_topic(topic)
    reasons = explain_gate(score)
    if reasons:
        raise ValueError("topic is not eligible: " + "; ".join(reasons))
    content_id = f"leo-{run_date.replace('-', '')}-{_slug(topic['id'])}"
    task_dir = root / "drafts" / f"{run_date}-{_slug(topic['id'])}"
    task_dir.mkdir(parents=True, exist_ok=False)
    (task_dir / "images").mkdir()
    manifest = {
        "content_id": content_id,
        "topic_id": topic["id"],
        "title": topic["title"],
        "category": topic["category"],
        "status": ContentStatus.RESEARCHING.value,
        "score": {**topic["scores"], "total": score.total},
        "trigger": topic.get("trigger", ""),
        "audience": topic.get("audience", ""),
        "demand_evidence": topic.get("demand_evidence", []),
        "differentiation": topic.get("differentiation", ""),
        "platforms": {
            "wechat": {"status": "empty"},
            "xhs": {"status": "empty"},
        },
        "sources": [],
        "claims": [],
        "risks": [],
        "history": [
            {
                "from": "idea",
                "to": "researching",
                "at": _now(),
                "note": "task created",
            }
        ],
    }
    save_yaml(task_dir / "manifest.yaml", manifest)
    for name, heading in (
        ("00-brief.md", "选题说明"),
        ("01-source-pack.md", "资料与来源"),
        ("02-master-draft.md", "内容母稿"),
        ("03-wechat-final.md", "公众号终稿"),
        ("04-xhs-final.md", "小红书终稿"),
        ("05-quality-report.md", "质量报告"),
    ):
        (task_dir / name).write_text(f"# {heading}\n", encoding="utf-8")
    return task_dir


def load_manifest(task_dir: Path) -> dict:
    return load_yaml(task_dir / "manifest.yaml")


def transition(
    task_dir: Path, target: ContentStatus, note: str = ""
) -> dict:
    manifest = load_manifest(task_dir)
    current = ContentStatus(manifest["status"])
    if target not in TRANSITIONS.get(current, set()):
        raise ValueError(
            f"illegal transition: {current.value} -> {target.value}"
        )
    manifest["status"] = target.value
    manifest.setdefault("history", []).append(
        {
            "from": current.value,
            "to": target.value,
            "at": _now(),
            "note": note,
        }
    )
    save_yaml(task_dir / "manifest.yaml", manifest)
    return manifest
