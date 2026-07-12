from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class ContentStatus(StrEnum):
    IDEA = "idea"
    RESEARCHING = "researching"
    DRAFTING = "drafting"
    QA_FAILED = "qa_failed"
    QA_PASSED = "qa_passed"
    AWAITING_REVIEW = "awaiting_review"
    APPROVED = "approved"
    REVISION_REQUESTED = "revision_requested"
    REJECTED = "rejected"
    READY_TO_PUBLISH = "ready_to_publish"
    PUBLISHED = "published"
    MEASURED = "measured"
    LEARNED = "learned"


@dataclass(frozen=True)
class TopicScore:
    demand_timeliness: int
    hook_strength: int
    consumption_value: int
    evidence: int
    differentiation: int
    account_fit: int

    @property
    def total(self) -> int:
        return sum(
            (
                self.demand_timeliness,
                self.hook_strength,
                self.consumption_value,
                self.evidence,
                self.differentiation,
                self.account_fit,
            )
        )

    @property
    def eligible(self) -> bool:
        return self.total >= 75 and self.demand_timeliness >= 15


@dataclass
class QAItem:
    code: str
    level: str
    message: str
    path: str = ""


@dataclass
class QAReport:
    passed: bool
    items: list[QAItem] = field(default_factory=list)


@dataclass(frozen=True)
class DailyOutcome:
    status: str
    message: str
    artifact: Path | None = None
