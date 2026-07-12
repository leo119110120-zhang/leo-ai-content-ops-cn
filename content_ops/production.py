from pathlib import Path

from content_ops import prompts
from content_ops.cards import render_wechat_cover, render_xhs_cards
from content_ops.config import load_yaml, save_yaml
from content_ops.models import ContentStatus
from content_ops.quality import run_quality_checks, write_quality_report
from content_ops.review import render_review
from content_ops.storage import create_task, transition


def _usage(result) -> dict:
    return {
        "model": result.model,
        "input_tokens": result.usage.input_tokens,
        "output_tokens": result.usage.output_tokens,
        "cached_tokens": result.usage.cached_tokens,
    }


def _validate_source_pack(source_pack: dict, source_inputs: list[dict]) -> None:
    prompts.require_fields(
        source_pack,
        {"sources", "claims", "risks", "markdown"},
        "source_pack",
    )
    input_source_ids = {source["id"] for source in source_inputs}
    output_source_ids = {source["id"] for source in source_pack["sources"]}
    if not output_source_ids or not output_source_ids.issubset(
        input_source_ids
    ):
        raise ValueError("source_pack referenced unknown sources")
    for claim in source_pack["claims"]:
        claim_source_ids = set(claim.get("source_ids", []))
        if not claim_source_ids or not claim_source_ids.issubset(
            output_source_ids
        ):
            raise ValueError("source_pack claim referenced unknown sources")


def _manifest_sources(source_inputs: list[dict]) -> list[dict]:
    return [
        {
            "id": source["id"],
            "kind": source["kind"],
            "path": source["location"],
            "retrieved_at": source.get("retrieved_at", ""),
        }
        for source in source_inputs
    ]


def produce_selected_candidate(
    content_root: Path,
    batch_path: Path,
    model,
    brand: dict,
) -> Path:
    batch = load_yaml(batch_path)
    if batch.get("status") != "selected":
        raise ValueError("candidate batch is not selected")
    topic = next(
        candidate
        for candidate in batch["candidates"]
        if candidate["id"] == batch["selected_id"]
    )
    topic_source_ids = set(topic["source_ids"])
    source_inputs = [
        source
        for source in batch["sources"]
        if source["id"] in topic_source_ids
    ]
    if not source_inputs:
        raise ValueError("selected candidate has no valid source snapshot")

    source_result = model.complete_json(
        stage="source_pack",
        system=prompts.SOURCE_PACK_SYSTEM,
        payload={"topic": topic, "sources": source_inputs},
    )
    source_pack = source_result.data
    _validate_source_pack(source_pack, source_inputs)

    task = create_task(content_root, topic, batch["run_date"])
    (task / "00-brief.md").write_text(
        f"# 选题说明\n\n{topic['trigger']}\n", encoding="utf-8"
    )
    (task / "01-source-pack.md").write_text(
        source_pack["markdown"], encoding="utf-8"
    )
    manifest = load_yaml(task / "manifest.yaml")
    manifest["sources"] = _manifest_sources(source_inputs)
    manifest["claims"] = source_pack["claims"]
    manifest["risks"] = source_pack["risks"]
    manifest["model_usage"] = {"source_pack": _usage(source_result)}
    save_yaml(task / "manifest.yaml", manifest)
    transition(task, ContentStatus.DRAFTING, "source pack ready")

    master_result = model.complete_json(
        stage="master_draft",
        system=prompts.MASTER_DRAFT_SYSTEM,
        payload={"topic": topic, "source_pack": source_pack},
    )
    master = master_result.data
    prompts.require_fields(master, {"markdown"}, "master_draft")
    (task / "02-master-draft.md").write_text(
        master["markdown"], encoding="utf-8"
    )

    copy_result = model.complete_json(
        stage="platform_copy",
        system=prompts.PLATFORM_COPY_SYSTEM,
        payload={
            "topic": topic,
            "master": master,
            "source_pack": source_pack,
        },
    )
    copy = copy_result.data
    prompts.require_fields(copy, {"wechat", "xhs"}, "platform_copy")
    (task / "03-wechat-final.md").write_text(
        copy["wechat"], encoding="utf-8"
    )
    (task / "04-xhs-final.md").write_text(
        copy["xhs"], encoding="utf-8"
    )

    packaging_result = model.complete_json(
        stage="packaging",
        system=prompts.PACKAGING_SYSTEM,
        payload={"topic": topic, "copy": copy},
    )
    packaging = packaging_result.data
    prompts.require_fields(
        packaging,
        {
            "titles",
            "covers",
            "openings",
            "reader_payoff",
            "discussion_question",
            "xhs_cards",
        },
        "packaging",
    )
    manifest = load_yaml(task / "manifest.yaml")
    manifest["packaging"] = {
        key: packaging[key]
        for key in (
            "titles",
            "covers",
            "openings",
            "reader_payoff",
            "discussion_question",
        )
    }
    manifest["xhs_cards"] = packaging["xhs_cards"]
    manifest["platforms"] = {
        "wechat": {"status": "drafted"},
        "xhs": {"status": "drafted"},
    }
    manifest["model_usage"].update(
        {
            "master_draft": _usage(master_result),
            "platform_copy": _usage(copy_result),
            "packaging": _usage(packaging_result),
        }
    )
    save_yaml(task / "manifest.yaml", manifest)

    render_wechat_cover(task, brand)
    render_xhs_cards(task, brand)
    report = run_quality_checks(task)
    write_quality_report(task, report)
    transition(
        task,
        ContentStatus.QA_PASSED if report.passed else ContentStatus.QA_FAILED,
        "automated QA",
    )
    if report.passed:
        transition(
            task,
            ContentStatus.AWAITING_REVIEW,
            "review package ready",
        )
        render_review(task, task / "review.html")
    return task
