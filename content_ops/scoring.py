from content_ops.models import TopicScore


LIMITS = {
    "demand_timeliness": 25,
    "hook_strength": 20,
    "consumption_value": 20,
    "evidence": 15,
    "differentiation": 10,
    "account_fit": 10,
}


def score_topic(topic: dict) -> TopicScore:
    values = topic.get("scores", {})
    for name, maximum in LIMITS.items():
        value = values.get(name)
        if not isinstance(value, int) or not 0 <= value <= maximum:
            raise ValueError(
                f"{name} must be an integer from 0 to {maximum}"
            )
    return TopicScore(**{name: values[name] for name in LIMITS})


def explain_gate(score: TopicScore) -> list[str]:
    reasons = []
    if score.demand_timeliness < 15:
        reasons.append("demand_timeliness must be at least 15")
    if score.total < 75:
        reasons.append("total score must be at least 75")
    return reasons
