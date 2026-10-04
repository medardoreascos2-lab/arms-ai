"""Canonical memory domains and sensitivity labels for MEDAR."""

from enum import Enum


class MemoryDomain(str, Enum):
    WORKING = "WORKING"
    EPISODIC = "EPISODIC"
    SEMANTIC = "SEMANTIC"
    PERSONAL = "PERSONAL"
    TECHNICAL = "TECHNICAL"
    TRADING = "TRADING"
    FINANCIAL = "FINANCIAL"
    BUSINESS = "BUSINESS"
    ROSITA = "ROSITA"
    TOOL = "TOOL"
    RESEARCH = "RESEARCH"


class MemorySensitivity(str, Enum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    SENSITIVE = "SENSITIVE"
    RESTRICTED = "RESTRICTED"


DURABLE_MEMORY_DOMAINS = frozenset(domain for domain in MemoryDomain if domain is not MemoryDomain.WORKING)


def is_durable_domain(domain: MemoryDomain) -> bool:
    if not isinstance(domain, MemoryDomain):
        raise TypeError("domain must be MemoryDomain")
    return domain in DURABLE_MEMORY_DOMAINS
