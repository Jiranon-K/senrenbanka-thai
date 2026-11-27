from __future__ import annotations

from . import ledger, prompt, runner
from . import workspace as workspace_module
from .shapes import MAJOR, MINOR, REVIEW_STAGE, REVIEWER, Finding
from .workspace import Workspace

SCHEMA = {
    "type": "object",
    "properties": {"flags": {"type": "array", "items": {
        "type": "object",
        "properties": {"idx": {"type": "string"}, "rule": {"type": "string"},
                       "severity": {"type": "string", "enum": [MAJOR, MINOR]},
                       "problem": {"type": "string"}},
        "required": ["idx", "rule", "severity", "problem"],
        "additionalProperties": False}}},
    "required": ["flags"], "additionalProperties": False,
}


def select_requests(workspace: Workspace, selection: runner.Selection) -> list:
    return [runner.StageRequest(chunk, ())
            for chunk in runner.build_chunks(workspace, selection)]


def store(workspace: Workspace, request: runner.StageRequest, payload: dict) -> runner.Outcome:
    chapter = request.chunk.chapter
    reviewed = {record.idx for record in request.chunk.records}
    flags = payload.get("flags", [])
    kept = [Finding(chapter, flag["idx"], flag["rule"], flag["severity"], flag["problem"],
                    REVIEWER)
            for flag in flags if flag["idx"] in reviewed]
    path = workspace.flags_file(chapter)
    elsewhere = [found for found in workspace_module.read_findings(path)
                 if found.idx not in reviewed]
    workspace_module.write_shapes(path, elsewhere + kept)
    dropped = len(flags) - len(kept)
    return runner.Outcome(len(kept), dropped, "%d flags kept, %d dropped for an idx outside "
                          "the chunk" % (len(kept), dropped))


def projected_output_tokens(request: runner.StageRequest) -> int:
    return len(request.chunk.records) * ledger.REVIEWER_OUTPUT_TOKENS_PER_RECORD


STAGE = runner.Stage(
    name=REVIEW_STAGE,
    role=prompt.REVIEWER_ROLE,
    heading="Review these lines:",
    schema=SCHEMA,
    select_requests=select_requests,
    store=store,
    projected_output_tokens=projected_output_tokens)
