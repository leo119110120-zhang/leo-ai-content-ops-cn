from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ModelUsage:
    input_tokens: int
    output_tokens: int
    cached_tokens: int = 0


@dataclass(frozen=True)
class ModelResult:
    data: dict
    usage: ModelUsage
    model: str


class StructuredModel(Protocol):
    def complete_json(
        self,
        *,
        stage: str,
        system: str,
        payload: dict,
        thinking: bool = False,
    ) -> ModelResult: ...
