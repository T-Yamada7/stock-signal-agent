from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class Signal:
    symbol: str
    name: str
    theme: str
    action: str            # "buy_candidate" | "watch"
    conviction: float      # 0.0–1.0
    reasons: list[str]
    risk_notes: str
    metrics: dict[str, Any] = field(default_factory=dict)
    generated_at: str = ""
    llm_comment: str = ""

    def to_dict(self) -> dict:
        return asdict(self)
