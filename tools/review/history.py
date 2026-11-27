from __future__ import annotations

from dataclasses import dataclass

from . import workspace as workspace_module
from .workspace import Workspace


@dataclass(frozen=True)
class LoggedChange:
    chapter: str
    idx: str
    speaker: str
    jp: str
    before: str
    after: str
    rules: tuple
    problem: str


@dataclass(frozen=True)
class LineHistory:
    chapter: str
    idx: str
    speaker: str
    jp: str
    original: str
    entries: tuple


def logged_change_from_fields(fields: dict) -> LoggedChange:
    return LoggedChange(fields["chapter"], fields["idx"], fields["speaker"], fields["jp"],
                        fields["before"], fields["after"], tuple(fields["rules"]),
                        fields["problem"])


def load_logged_changes(workspace: Workspace) -> list[LoggedChange]:
    return [logged_change_from_fields(fields)
            for fields in workspace_module.read_json_lines(workspace.changes_file)]


def line_history(entries: list[LoggedChange]) -> LineHistory:
    first = entries[0]
    return LineHistory(first.chapter, first.idx, first.speaker, first.jp, first.before,
                       tuple(entries))


def load_histories(workspace: Workspace) -> dict[tuple, LineHistory]:
    grouped: dict[tuple, list[LoggedChange]] = {}
    for logged in load_logged_changes(workspace):
        grouped.setdefault((logged.chapter, logged.idx), []).append(logged)
    return {line: line_history(entries) for line, entries in grouped.items()}


def entries_since_original(line: LineHistory) -> tuple:
    leading: list[LoggedChange] = []
    for entry in line.entries:
        leading = [] if entry.after == line.original else leading + [entry]
    return tuple(leading) or line.entries
