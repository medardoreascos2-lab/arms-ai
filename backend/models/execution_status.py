from dataclasses import dataclass


@dataclass
class ExecutionStatus:
    status: str
    reason: str

    APPROVED = "APPROVED"
    BLOCKED_RISK = "BLOCKED_RISK"
    BLOCKED_SETUP = "BLOCKED_SETUP"
