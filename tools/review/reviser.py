from __future__ import annotations

import dataclasses
import functools

from . import ledger, lint, prompt, runner
from . import workspace as workspace_module
from .shapes import LINT, MAJOR, REVISE_STAGE, Finding, Record, Revision
from .tables import Tables, load_tables
from .workspace import Workspace, mt

FULL_RETRANSLATION = "FULL"
ACCEPTANCE_RULES = ("F1", "F2", "F3", "F5", "N2")
LINE_BREAKS = str.maketrans({"\t": " ", "\r": " ", "\n": " "})

SCHEMA = {
    "type": "object",
    "properties": {"lines": {"type": "array", "items": {
        "type": "object",
        "properties": {"idx": {"type": "string"}, "th": {"type": "string"}},
        "required": ["idx", "th"], "additionalProperties": False}}},
    "required": ["lines"], "additionalProperties": False,
}


@functools.lru_cache(maxsize=4)
def lint_tables(workspace: Workspace) -> Tables:
    return load_tables(workspace, lint.SUMMARIZATION_RATIO)


def full_retranslation(record: Record) -> Finding:
    return Finding(record.chapter, record.idx, FULL_RETRANSLATION, MAJOR,
                   "retranslate the whole line from the Japanese", LINT)


def open_findings(record: Record, tables: Tables, flags: list, revision: Revision | None,
                  full: bool) -> list[Finding]:
    if revision and revision.before == record.th:
        return []
    if revision and revision.after == record.th:
        return flags
    mechanical = lint.lint_record(record, tables)
    return mechanical + ([full_retranslation(record)] if full else []) + flags


def chapter_findings(workspace: Workspace, chapter: str, records: tuple, full: bool) -> list:
    flags: dict[str, list[Finding]] = {}
    for found in workspace_module.read_findings(workspace.flags_file(chapter)):
        flags.setdefault(found.idx, []).append(found)
    revisions = {revision.idx: revision for revision
                 in workspace_module.read_revisions(workspace.revised_file(chapter))}
    return [found for record in records
            for found in open_findings(record, lint_tables(workspace),
                                       flags.get(record.idx, []),
                                       revisions.get(record.idx), full)]


def select_requests(workspace: Workspace, selection: runner.Selection) -> list:
    requests = [runner.StageRequest(chunk, tuple(chapter_findings(
                    workspace, chunk.chapter, chunk.records,
                    chunk.chapter in selection.full_chapters)))
                for chunk in runner.build_chunks(workspace, selection)]
    return [request for request in requests if request.findings]


def clean(thai: str) -> str:
    return mt.normalize(thai).translate(LINE_BREAKS).strip()


def revision_for(record: Record, after: str, findings: tuple) -> Revision:
    own = [found for found in findings if found.idx == record.idx]
    return Revision(record.chapter, record.idx, record.th, after,
                    tuple(dict.fromkeys(found.rule for found in own)),
                    "; ".join(found.problem for found in own))


def broken_rules(workspace: Workspace, record: Record, after: str) -> list[str]:
    return [found.rule for found in lint.lint_record(
        dataclasses.replace(record, th=after), lint_tables(workspace), ACCEPTANCE_RULES)]


def reject(workspace: Workspace, record: Record, after: str, broken: list[str]) -> None:
    print("REJECTED %s %s fails %s" % (record.chapter, record.idx, " ".join(broken)))
    workspace_module.append_json_line(workspace.rejected_file, {
        "chapter": record.chapter, "idx": record.idx, "rules": broken, "th": after})


def save_revisions(workspace: Workspace, chapter: str, accepted: dict) -> None:
    path = workspace.revised_file(chapter)
    kept = [revision for revision in workspace_module.read_revisions(path)
            if revision.idx not in accepted]
    workspace_module.write_shapes(path, kept + list(accepted.values()))


def store(workspace: Workspace, request: runner.StageRequest, payload: dict) -> runner.Outcome:
    requested = {found.idx for found in request.findings}
    records = {record.idx: record for record in request.chunk.records}
    lines = payload.get("lines", [])
    answers = {line["idx"]: clean(line["th"]) for line in lines if line["idx"] in requested}
    broken = {idx: broken_rules(workspace, records[idx], after)
              for idx, after in answers.items()}
    for idx, after in answers.items():
        if broken[idx]:
            reject(workspace, records[idx], after, broken[idx])
    accepted = {idx: revision_for(records[idx], after, request.findings)
                for idx, after in answers.items()
                if not broken[idx] and after != records[idx].th}
    save_revisions(workspace, request.chunk.chapter, accepted)
    rejected = sum(1 for rules in broken.values() if rules)
    unrequested = sum(1 for line in lines if line["idx"] not in requested)
    return runner.Outcome(
        len(accepted), rejected + unrequested,
        "%d of %d requested lines revised, %d rejected, %d not requested, %d unchanged, "
        "%d not returned"
        % (len(accepted), len(requested), rejected, unrequested,
           len(answers) - rejected - len(accepted), len(requested) - len(answers)))


def projected_output_tokens(request: runner.StageRequest) -> int:
    return len({found.idx for found in request.findings}) * ledger.THAI_TOKENS_PER_RECORD


STAGE = runner.Stage(
    name=REVISE_STAGE,
    role=prompt.REVISER_ROLE,
    heading="Lines (rewrite only those that carry findings):",
    schema=SCHEMA,
    select_requests=select_requests,
    store=store,
    projected_output_tokens=projected_output_tokens)
