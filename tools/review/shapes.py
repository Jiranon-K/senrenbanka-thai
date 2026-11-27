from __future__ import annotations

from dataclasses import dataclass

MAJOR = "major"
MINOR = "minor"
LINT = "lint"
REVIEWER = "reviewer"
REVIEW_STAGE = "review"
REVISE_STAGE = "revise"
ARBITRATE_STAGE = "arbitrate"
ORIGINAL = "original"
CURRENT = "current"
SAME = "same"


@dataclass(frozen=True)
class Record:
    chapter: str
    idx: str
    speaker: str
    jp: str
    en: str
    th: str


@dataclass(frozen=True)
class Finding:
    chapter: str
    idx: str
    rule: str
    severity: str
    problem: str
    source: str


@dataclass(frozen=True)
class Revision:
    chapter: str
    idx: str
    before: str
    after: str
    rules: tuple
    problem: str


@dataclass(frozen=True)
class Contest:
    record: Record
    preceding: tuple
    original: str


@dataclass(frozen=True)
class Arbitration:
    chapter: str
    idx: str
    original: str
    current: str
    verdict: str
    reason: str


@dataclass(frozen=True)
class LedgerEntry:
    stage: str
    request_id: str
    model: str
    batch: bool
    usage: dict


def revision_from_fields(fields: dict) -> Revision:
    return Revision(fields["chapter"], fields["idx"], fields["before"], fields["after"],
                    tuple(fields["rules"]), fields["problem"])
