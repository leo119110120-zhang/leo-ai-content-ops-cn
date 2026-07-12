from pathlib import Path

from content_ops.config import load_yaml, save_yaml
from content_ops.prompts import CANDIDATE_SYSTEM, require_fields
from content_ops.scoring import score_topic


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
    valid_source_ids = {source["id"] for source in sources}
    candidates: list[dict] = []
    score_errors: list[ValueError] = []
    valid_score_count = 0
    model_candidates = result.data.get("candidates", [])
    for item in model_candidates:
        require_fields(item, REQUIRED, "candidate")
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
