from __future__ import annotations

import collections
import hashlib
import json

from . import history, ledger, prompt, runner
from . import workspace as workspace_module
from .shapes import ARBITRATE_STAGE, CURRENT, ORIGINAL, SAME, Arbitration, Contest, Record
from .workspace import Workspace

FIRST_LABEL = "X"
SECOND_LABEL = "Y"
PRECEDING_RECORDS = 3
CONTESTS_PER_REQUEST = runner.CHUNK_RECORDS
VERDICTS = (ORIGINAL, CURRENT, SAME)

SCHEMA = {
    "type": "object",
    "properties": {"choices": {"type": "array", "items": {
        "type": "object",
        "properties": {"idx": {"type": "string"},
                       "better": {"type": "string",
                                  "enum": [FIRST_LABEL, SECOND_LABEL, SAME]},
                       "reason": {"type": "string"}},
        "required": ["idx", "better", "reason"],
        "additionalProperties": False}}},
    "required": ["choices"], "additionalProperties": False,
}


def original_label(chapter: str, idx: str) -> str:
    digest = hashlib.sha256(("%s\t%s" % (chapter, idx)).encode("utf-8")).digest()
    return SECOND_LABEL if digest[0] % 2 else FIRST_LABEL


def candidates(contest: Contest) -> dict:
    original_first = original_label(contest.record.chapter, contest.record.idx) == FIRST_LABEL
    texts = (contest.original, contest.record.th) if original_first \
        else (contest.record.th, contest.original)
    return {FIRST_LABEL: texts[0], SECOND_LABEL: texts[1]}


def verdict_for(chapter: str, idx: str, better: str) -> str:
    if better == SAME:
        return SAME
    return ORIGINAL if better == original_label(chapter, idx) else CURRENT


def chapter_contests(records: list[Record], originals: dict) -> list[Contest]:
    return [Contest(record, tuple(records[max(0, position - PRECEDING_RECORDS):position]),
                    originals[record.idx])
            for position, record in enumerate(records)
            if originals.get(record.idx) and originals[record.idx] != record.th]


def already_judged(workspace: Workspace, chapter: str) -> set:
    return {(stored.idx, stored.original, stored.current) for stored
            in workspace_module.read_arbitrations(workspace.arbitration_file(chapter))}


def request_for(chapter: str, number: int, contests: list[Contest]) -> runner.StageRequest:
    chunk = runner.Chunk("%s-%04d" % (chapter, number), chapter, (),
                         tuple(contest.record for contest in contests))
    return runner.StageRequest(chunk, (), tuple(contests))


def chapter_requests(workspace: Workspace, chapter: str, contests: list[Contest]) -> list:
    judged = already_judged(workspace, chapter)
    groups = [[contest for contest in contests[start:start + CONTESTS_PER_REQUEST]
               if (contest.record.idx, contest.original, contest.record.th) not in judged]
              for start in range(0, len(contests), CONTESTS_PER_REQUEST)]
    return [request_for(chapter, number, pending)
            for number, pending in enumerate(groups) if pending]


def select_requests(workspace: Workspace, selection: runner.Selection) -> list:
    grouped = workspace_module.group_by_chapter(workspace_module.load_records(workspace))
    originals: dict[str, dict] = {}
    for (chapter, idx), line in history.load_histories(workspace).items():
        originals.setdefault(chapter, {})[idx] = line.original
    return [request for chapter in runner.chosen_chapters(workspace, selection, grouped)
            for request in chapter_requests(
                workspace, chapter,
                chapter_contests(grouped[chapter], originals.get(chapter, {})))]


def context_fields(record: Record) -> dict:
    return {"speaker": record.speaker or prompt.NARRATION_LABEL, "jp": record.jp,
            "th": record.th}


def contest_fields(contest: Contest) -> dict:
    return {"idx": contest.record.idx,
            "speaker": contest.record.speaker or prompt.NARRATION_LABEL,
            "jp": contest.record.jp,
            "context": [context_fields(record) for record in contest.preceding],
            **candidates(contest)}


def user_message(heading: str, request: runner.StageRequest) -> str:
    return heading + "\n" + json.dumps(
        [contest_fields(contest) for contest in request.contests], ensure_ascii=False)


def save_arbitrations(workspace: Workspace, chapter: str, decided: list[Arbitration]) -> None:
    path = workspace.arbitration_file(chapter)
    replaced = {arbitration.idx for arbitration in decided}
    kept = [stored for stored in workspace_module.read_arbitrations(path)
            if stored.idx not in replaced]
    workspace_module.write_shapes(path, kept + decided)


def store(workspace: Workspace, request: runner.StageRequest, payload: dict) -> runner.Outcome:
    chapter = request.chunk.chapter
    contests = {contest.record.idx: contest for contest in request.contests}
    choices = payload.get("choices", [])
    answered = {choice["idx"]: choice for choice in choices if choice["idx"] in contests}
    decided = [Arbitration(chapter, idx, contests[idx].original, contests[idx].record.th,
                           verdict_for(chapter, idx, choice["better"]), choice["reason"])
               for idx, choice in answered.items()]
    save_arbitrations(workspace, chapter, decided)
    verdicts = collections.Counter(arbitration.verdict for arbitration in decided)
    unrequested = sum(1 for choice in choices if choice["idx"] not in contests)
    return runner.Outcome(
        len(decided), unrequested,
        "%d original, %d current, %d same, %d not requested, %d not returned"
        % (verdicts[ORIGINAL], verdicts[CURRENT], verdicts[SAME], unrequested,
           len(contests) - len(decided)))


def projected_input_tokens(request: runner.StageRequest) -> int:
    return len(request.contests) * ledger.ARBITER_INPUT_TOKENS_PER_LINE


def projected_output_tokens(request: runner.StageRequest) -> int:
    return len(request.contests) * ledger.ARBITER_OUTPUT_TOKENS_PER_LINE


def remembered_contest(contest: Contest) -> dict:
    return {"idx": contest.record.idx, "speaker": contest.record.speaker,
            "jp": contest.record.jp, "original": contest.original,
            "current": contest.record.th}


def bookkeeping_fields(requests: list) -> dict:
    return {"contests": {request.chunk.request_id: {
        "chapter": request.chunk.chapter,
        "lines": [remembered_contest(contest) for contest in request.contests]}
        for request in requests}}


def restored_request(request_id: str, remembered: dict) -> runner.StageRequest:
    chapter = remembered["chapter"]
    contests = tuple(Contest(Record(chapter, line["idx"], line["speaker"], line["jp"], "",
                                    line["current"]), (), line["original"])
                     for line in remembered["lines"])
    chunk = runner.Chunk(request_id, chapter, (),
                         tuple(contest.record for contest in contests))
    return runner.StageRequest(chunk, (), contests)


def restore_requests(workspace: Workspace, entry: dict) -> dict:
    return {request_id: restored_request(request_id, remembered)
            for request_id, remembered in entry["contests"].items()}


STAGE = runner.Stage(
    name=ARBITRATE_STAGE,
    role=prompt.ARBITER_ROLE,
    heading="Choose the more faithful candidate for each line:",
    schema=SCHEMA,
    select_requests=select_requests,
    store=store,
    projected_output_tokens=projected_output_tokens,
    user_message=user_message,
    projected_input_tokens=projected_input_tokens,
    bookkeeping_fields=bookkeeping_fields,
    restore_requests=restore_requests)
