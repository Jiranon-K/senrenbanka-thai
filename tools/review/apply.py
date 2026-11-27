from __future__ import annotations

import csv
import dataclasses
import os
from dataclasses import dataclass

from . import workspace as workspace_module
from .shapes import REVIEWER, Record, Revision
from .workspace import Workspace, tsv

BYTE_ORDER_MARK = b"\xef\xbb\xbf"
WINDOWS_ENDING = b"\r\n"
UNIX_ENDING = b"\n"
FIELD_SEPARATOR = "\t"


@dataclass(frozen=True)
class ThaiLine:
    raw: bytes
    idx: str
    text: str
    ending: bytes


@dataclass(frozen=True)
class ThaiFile:
    has_byte_order_mark: bool
    lines: tuple

    @property
    def ending(self) -> bytes:
        return WINDOWS_ENDING if any(line.ending == WINDOWS_ENDING for line in self.lines) \
            else UNIX_ENDING


@dataclass(frozen=True)
class ChapterResult:
    chapter: str
    applied: tuple
    already_applied: int
    stale: int


def parse_line(raw: bytes) -> ThaiLine:
    body = raw.rstrip(b"\r\n")
    fields = body.decode("utf-8").split(FIELD_SEPARATOR, 1)
    return ThaiLine(raw, fields[0] if body.strip() else "", "".join(fields[1:]),
                    raw[len(body):])


def parse_thai_file(content: bytes) -> ThaiFile:
    has_byte_order_mark = content.startswith(BYTE_ORDER_MARK)
    body = content[len(BYTE_ORDER_MARK):] if has_byte_order_mark else content
    return ThaiFile(has_byte_order_mark,
                    tuple(parse_line(raw) for raw in body.splitlines(keepends=True)))


def read_thai_file(path: str) -> ThaiFile:
    if not os.path.exists(path):
        return ThaiFile(False, ())
    with open(path, "rb") as thai_file:
        return parse_thai_file(thai_file.read())


def serialize_thai_file(thai_file: ThaiFile) -> bytes:
    return (BYTE_ORDER_MARK if thai_file.has_byte_order_mark else b"") \
        + b"".join(line.raw for line in thai_file.lines)


def rewritten_line(idx: str, text: str, ending: bytes) -> ThaiLine:
    return ThaiLine((idx + FIELD_SEPARATOR + text).encode("utf-8") + ending, idx, text, ending)


def replace_text(thai_file: ThaiFile, revision: Revision) -> ThaiFile:
    return dataclasses.replace(thai_file, lines=tuple(
        rewritten_line(line.idx, revision.after, line.ending)
        if line.idx == revision.idx else line
        for line in thai_file.lines))


def insert_line(thai_file: ThaiFile, revision: Revision, chapter_order: list[str]) -> ThaiFile:
    earlier = set(chapter_order[:chapter_order.index(revision.idx)]) \
        if revision.idx in chapter_order else set(chapter_order)
    position = max((number + 1 for number, line in enumerate(thai_file.lines)
                    if line.idx in earlier), default=0)
    lines = list(thai_file.lines)
    if position and not lines[position - 1].ending:
        previous = lines[position - 1]
        lines[position - 1] = rewritten_line(previous.idx, previous.text, thai_file.ending)
    lines.insert(position, rewritten_line(revision.idx, revision.after, thai_file.ending))
    return dataclasses.replace(thai_file, lines=tuple(lines))


def apply_revisions(chapter: str, thai_file: ThaiFile, revisions: list[Revision],
                    chapter_order: list[str]) -> tuple[ThaiFile, ChapterResult]:
    applied: list[Revision] = []
    already_applied = stale = 0
    for revision in revisions:
        current = {line.idx: line.text for line in thai_file.lines if line.idx}
        if current.get(revision.idx, "") == revision.after:
            already_applied += 1
        elif current.get(revision.idx, "") != revision.before:
            stale += 1
        elif revision.idx in current:
            thai_file = replace_text(thai_file, revision)
            applied.append(revision)
        else:
            thai_file = insert_line(thai_file, revision, chapter_order)
            applied.append(revision)
    return thai_file, ChapterResult(chapter, tuple(applied), already_applied, stale)


def change_fields(revision: Revision, record: Record) -> dict:
    return {**dataclasses.asdict(revision), "rules": list(revision.rules),
            "speaker": record.speaker, "jp": record.jp}


def change_key(fields: dict) -> tuple:
    return fields["chapter"], fields["idx"], fields["before"], fields["after"]


def log_changes(workspace: Workspace, applied: tuple, records: dict) -> None:
    logged = {change_key(fields)
              for fields in workspace_module.read_json_lines(workspace.changes_file)}
    for revision in applied:
        fields = change_fields(revision, records[revision.idx])
        if change_key(fields) not in logged:
            workspace_module.append_json_line(workspace.changes_file, fields)


def close_reviewer_flags(workspace: Workspace, chapter: str, resolved: set) -> None:
    path = workspace.flags_file(chapter)
    flags = workspace_module.read_findings(path)
    remaining = [found for found in flags
                 if not (found.source == REVIEWER and found.idx in resolved)]
    if len(remaining) != len(flags):
        workspace_module.write_shapes(path, remaining)


def apply_chapter(workspace: Workspace, chapter: str, records: list[Record]) -> ChapterResult:
    revisions = workspace_module.read_revisions(workspace.revised_file(chapter))
    path = workspace.thai_file(chapter)
    before = read_thai_file(path)
    after, result = apply_revisions(chapter, before, revisions,
                                    [record.idx for record in records])
    if result.applied:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as thai_file:
            thai_file.write(serialize_thai_file(after))
        log_changes(workspace, result.applied, {record.idx: record for record in records})
        close_reviewer_flags(workspace, chapter,
                             {revision.idx for revision in result.applied})
    return result


def mirror_into_strings(workspace: Workspace, chapters: list[str]) -> int:
    thai = {chapter: {line.idx: line.text
                      for line in read_thai_file(workspace.thai_file(chapter)).lines if line.idx}
            for chapter in chapters}
    with open(workspace.strings_csv, encoding="utf-8-sig", newline="") as strings_file:
        reader = csv.DictReader(strings_file)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    changed = 0
    for row in rows:
        text = thai.get(tsv.prefix(row["file"]), {}).get(row["idx"])
        if text is not None and row["th"] != text:
            row["th"] = text
            changed += 1
    if changed:
        with open(workspace.strings_csv, "w", encoding="utf-8-sig", newline="") as strings_file:
            writer = csv.DictWriter(strings_file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
    return changed


def revised_chapters(workspace: Workspace) -> list[str]:
    directory = os.path.dirname(workspace.revised_file(""))
    if not os.path.isdir(directory):
        return []
    return sorted(name[:-len(".json")] for name in os.listdir(directory)
                  if name.endswith(".json"))


def run(workspace: Workspace, chapters: list[str], everything: bool) -> int:
    grouped = workspace_module.group_by_chapter(workspace_module.load_records(workspace))
    wanted = revised_chapters(workspace) if everything else chapters
    results = [apply_chapter(workspace, chapter, grouped.get(chapter, []))
               for chapter in wanted]
    for result in results:
        print("%s: %d applied, %d already applied, %d stale (Thai changed since the revision)"
              % (result.chapter, len(result.applied), result.already_applied, result.stale))
    mirrored = mirror_into_strings(workspace, wanted)
    print("%d lines applied, %d rows updated in %s"
          % (sum(len(result.applied) for result in results), mirrored, workspace.strings_csv))
    return 0
