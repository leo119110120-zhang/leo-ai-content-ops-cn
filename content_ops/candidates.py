from pathlib import Path

from content_ops.config import load_yaml, save_yaml
from content_ops.contracts import (
    require_exact_fields,
    require_mapping,
    require_nonempty_string,
    require_string_list,
)
from content_ops.prompts import CANDIDATE_SYSTEM
from content_ops.scoring import LIMITS, score_topic


REQUIRED = {
    "id",
    "title",
    "category",
    "trigger",
    "audience",
    "demand_evidence",
    "differentiation",
    "risks",
    "source_ids",
    "scores",
}
STRING_FIELDS = {
    "id",
    "title",
    "category",
    "trigger",
    "audience",
    "differentiation",
}


def validate_candidate(candidate, label: str) -> dict:
    candidate = require_mapping(candidate, label)
    require_exact_fields(candidate, REQUIRED, label)
    for field in STRING_FIELDS:
        require_nonempty_string(candidate[field], f"{label}.{field}")
    require_string_list(
        candidate["demand_evidence"],
        f"{label}.demand_evidence",
        allow_empty=True,
    )
    require_string_list(
        candidate["risks"],
        f"{label}.risks",
        allow_empty=True,
    )
    require_string_list(candidate["source_ids"], f"{label}.source_ids")
    require_exact_fields(candidate["scores"], set(LIMITS), f"{label}.scores")
    return candidate


def generate_candidate_batch(
    run_date: str,
    sources: list[dict],
    model,
) -> dict:
    result = model.complete_json(
        stage="candidates",
        system=CANDIDATE_SYSTEM,
        payload={"run_date": run_date, "sources": sources, "limit": 3},
        thinking=True,
    )
    response = require_mapping(result.data, "candidate_response")
    require_exact_fields(response, {"candidates"}, "candidate_response")
    valid_source_ids = {source["id"] for source in sources}
    candidates: list[dict] = []
    score_errors: list[ValueError] = []
    valid_score_count = 0
    model_candidates = response["candidates"]
    if not isinstance(model_candidates, list):
        raise ValueError("candidate_response.candidates must be a list")
    seen_ids: set[str] = set()
    for index, raw_item in enumerate(model_candidates):
        item = validate_candidate(raw_item, f"candidate[{index}]")
        if item["id"] in seen_ids:
            raise ValueError("candidate ids must be unique")
        seen_ids.add(item["id"])
        if not item["demand_evidence"]:
            continue
        source_ids = item["source_ids"]
        if not source_ids or not set(source_ids).issubset(valid_source_ids):
            continue
        try:
            score = score_topic(item)
        except ValueError as error:
            score_errors.append(error)
            continue
        valid_score_count += 1
        if not score.eligible:
            continue
        item["scores"] = {**item["scores"], "total": score.total}
        candidates.append(item)
        if len(candidates) == 3:
            break
    if model_candidates and score_errors and valid_score_count == 0:
        raise ValueError(
            "candidate response contains no valid score schema"
        ) from score_errors[0]
    return {
        "run_date": run_date,
        "status": (
            "awaiting_topic_selection" if candidates else "no_candidates"
        ),
        "candidates": candidates,
        "sources": sources,
        "model_usage": {
            "input_tokens": result.usage.input_tokens,
            "output_tokens": result.usage.output_tokens,
            "cached_tokens": result.usage.cached_tokens,
        },
    }


class CandidateBatchStore:
    def __init__(self, path: Path):
        self.path = path

    def create(self, batch: dict) -> dict:
        if self.path.exists():
            raise FileExistsError(self.path)
        save_yaml(self.path, batch)
        return batch

    def select(self, candidate_id: str) -> dict:
        batch = load_yaml(self.path)
        if batch.get("status") == "selected":
            if batch.get("selected_id") == candidate_id:
                return batch
            raise ValueError("another candidate is already selected")
        if batch.get("status") != "awaiting_topic_selection":
            raise ValueError("batch is not awaiting topic selection")
        if candidate_id not in {
            candidate["id"] for candidate in batch["candidates"]
        }:
            raise ValueError("unknown candidate")
        batch["status"] = "selected"
        batch["selected_id"] = candidate_id
        save_yaml(self.path, batch)
        return batch
