from collections.abc import Mapping


def require_mapping(value, label: str) -> dict:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return dict(value)


def require_exact_fields(
    value: Mapping,
    fields: set[str],
    label: str,
) -> None:
    mapping = require_mapping(value, label)
    actual = set(mapping)
    missing = sorted(fields - actual)
    unexpected = sorted(actual - fields)
    if missing or unexpected:
        details = []
        if missing:
            details.append(f"missing={','.join(missing)}")
        if unexpected:
            details.append(f"unexpected={','.join(unexpected)}")
        raise ValueError(f"{label} has invalid fields: {'; '.join(details)}")


def require_nonempty_string(value, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value


def require_string_list(
    value,
    label: str,
    *,
    allow_empty: bool = False,
) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list of strings")
    if not allow_empty and not value:
        raise ValueError(f"{label} must not be empty")
    for index, item in enumerate(value):
        require_nonempty_string(item, f"{label}[{index}]")
    return value
