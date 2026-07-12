from pathlib import Path

from content_ops import prompts
from content_ops.cards import render_wechat_cover, render_xhs_cards
from content_ops.config import load_yaml, save_yaml
from content_ops.contracts import (
    require_exact_fields,
    require_mapping,
    require_nonempty_string,
    require_string_list,
)
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
    source_pack = require_mapping(source_pack, "source_pack")
    require_exact_fields(
        source_pack,
        {"sources", "claims", "risks", "markdown"},
        "source_pack",
    )
    if not isinstance(source_pack["sources"], list) or not source_pack["sources"]:
        raise ValueError("source_pack.sources must be a non-empty list")
    for index, raw_source in enumerate(source_pack["sources"]):
        source = require_mapping(raw_source, f"source_pack.sources[{index}]")
        require_nonempty_string(
            source.get("id"),
            f"source_pack.sources[{index}].id",
        )
    if not isinstance(source_pack["claims"], list) or not source_pack["claims"]:
        raise ValueError("source_pack.claims must be a non-empty list")
    require_string_list(
        source_pack["risks"],
        "source_pack.risks",
        allow_empty=True,
    )
    require_nonempty_string(source_pack["markdown"], "source_pack.markdown")
    input_source_ids = {source["id"] for source in source_inputs}
    output_source_ids = {source["id"] for source in source_pack["sources"]}
    if not output_source_ids or not output_source_ids.issubset(
        input_source_ids
    ):
        raise ValueError("source_pack referenced unknown sources")
    for index, raw_claim in enumerate(source_pack["claims"]):
        claim = require_mapping(raw_claim, f"source_pack.claims[{index}]")
        require_exact_fields(
            claim,
            {"text", "label", "source_ids"},
            f"source_pack.claims[{index}]",
        )
        require_nonempty_string(
            claim["text"],
            f"source_pack.claims[{index}].text",
        )
        require_nonempty_string(
            claim["label"],
            f"source_pack.claims[{index}].label",
        )
        require_string_list(
            claim["source_ids"],
            f"source_pack.claims[{index}].source_ids",
        )
        claim_source_ids = set(claim.get("source_ids", []))
        if not claim_source_ids or not claim_source_ids.issubset(
            output_source_ids
        ):
            raise ValueError("source_pack claim referenced unknown sources")


def _validate_master(master: dict) -> None:
    master = require_mapping(master, "master_draft")
    require_exact_fields(master, {"markdown"}, "master_draft")
    require_nonempty_string(master["markdown"], "master_draft.markdown")


def _validate_platform_copy(copy: dict) -> None:
    copy = require_mapping(copy, "platform_copy")
    require_exact_fields(copy, {"wechat", "xhs"}, "platform_copy")
    require_nonempty_string(copy["wechat"], "platform_copy.wechat")
    require_nonempty_string(copy["xhs"], "platform_copy.xhs")


def _require_exact_string_count(
    value,
    count: int,
    label: str,
) -> list[str]:
    items = require_string_list(value, label)
    if len(items) != count:
        raise ValueError(f"{label} must contain exactly {count} items")
    return items


def _validate_packaging(packaging: dict) -> None:
    packaging = require_mapping(packaging, "packaging")
    require_exact_fields(
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
    _require_exact_string_count(packaging["titles"], 5, "packaging.titles")
    _require_exact_string_count(packaging["covers"], 3, "packaging.covers")
    _require_exact_string_count(packaging["openings"], 2, "packaging.openings")
    require_nonempty_string(
        packaging["reader_payoff"],
        "packaging.reader_payoff",
    )
    require_nonempty_string(
        packaging["discussion_question"],
        "packaging.discussion_question",
    )
    cards = packaging["xhs_cards"]
    if not isinstance(cards, list) or not cards:
        raise ValueError("packaging.xhs_cards must be a non-empty list")
    for index, raw_card in enumerate(cards):
        card = require_mapping(raw_card, f"packaging.xhs_cards[{index}]")
        prompts.require_fields(
            card,
            {"layout", "eyebrow", "title", "body"},
            f"packaging.xhs_cards[{index}]",
        )
        for field in ("layout", "eyebrow", "title", "body"):
            require_nonempty_string(
                card[field],
                f"packaging.xhs_cards[{index}].{field}",
            )


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
    _validate_master(master)
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
    _validate_platform_copy(copy)
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
    _validate_packaging(packaging)
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
