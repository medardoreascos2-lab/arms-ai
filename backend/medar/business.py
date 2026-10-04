"""Advisory business management analysis contract."""

from dataclasses import dataclass
from enum import Enum
from typing import Mapping


class BusinessArea(str, Enum):
    KPI = "KPI"
    OPERATIONS = "OPERATIONS"
    SALES = "SALES"
    COSTS = "COSTS"
    STRATEGY = "STRATEGY"
    RISK = "RISK"
    PLANNING = "PLANNING"


@dataclass(frozen=True)
class BusinessManagementRequest:
    request_id: str
    goal: str
    areas: tuple[BusinessArea, ...]
    metrics: Mapping[str, float]
    constraints: tuple[str, ...]
    advisory_only: bool = True

    def __post_init__(self) -> None:
        if not self.request_id.strip() or not self.goal.strip() or not self.areas:
            raise ValueError("business request identity, goal, and areas are required")
        if any(not isinstance(area, BusinessArea) for area in self.areas):
            raise TypeError("business areas must be typed")
        if not self.advisory_only:
            raise ValueError("business management output must remain advisory")
