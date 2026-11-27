from __future__ import annotations

import dataclasses
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable

from . import ledger, prompt
from . import workspace as workspace_module
from .lint import SUMMARIZATION_RATIO
from .shapes import Finding, LedgerEntry, Record
from .tables import load_tables
from .workspace import Workspace, mt

MODEL = "claude-sonnet-5-5"
EFFORT = "medium"
MAX_TOKENS = 16000
CHUNK_RECORDS = mt.CHUNK
CONTEXT_RECORDS = mt.CONTEXT
SYNC_WORKERS = 4
SUCCESSFUL_STOP = "end_turn"
BATCH_ENDED = "ended"
BATCH_SUCCEEDED = "succeeded"


@dataclass(frozen=True)
class Selection:
    chapters: tuple
    everything: bool
    full_chapters: tuple
    limit: int


@dataclass(frozen=True)
class Chunk:
    request_id: str
    chapter: str
    context: tuple
    records: tuple


@dataclass(frozen=True)
class StageRequest:
    chunk: Chunk
    findings: tuple
    contests: tuple = ()


@dataclass(frozen=True)
class Outcome:
    accepted: int
    dropped: int
    detail: str


def findings_message(heading: str, request: StageRequest) -> str:
    return prompt.user_message(heading, request.chunk.context, request.chunk.records,
                               request.findings)


def findings_input_tokens(request: StageRequest) -> int:
    lines = len(request.chunk.context) + len(request.chunk.records)
    return (lines * (ledger.INPUT_TOKENS_PER_RECORD + ledger.THAI_TOKENS_PER_RECORD)
            + len(request.findings) * ledger.TOKENS_PER_FINDING)


def findings_bookkeeping(requests: list[StageRequest]) -> dict:
    return {"findings": {request.chunk.request_id: [dataclasses.asdict(found)
                                                    for found in request.findings]
                         for request in requests}}


def requests_from_findings(workspace: Workspace, entry: dict) -> dict[str, StageRequest]:
    selection = Selection(tuple(entry["chapters"]), entry["all"], tuple(entry["full"]), 0)
    chunks = {chunk.request_id: chunk for chunk in build_chunks(workspace, selection)}
    return {request_id: StageRequest(chunks[request_id],
                                     tuple(Finding(**fields) for fields in findings))
            for request_id, findings in entry["findings"].items() if request_id in chunks}


@dataclass(frozen=True)
class Stage:
    name: str
    role: str
    heading: str
    schema: dict
    select_requests: Callable
    store: Callable
    projected_output_tokens: Callable
    user_message: Callable = findings_message
    projected_input_tokens: Callable = findings_input_tokens
    bookkeeping_fields: Callable = findings_bookkeeping
    restore_requests: Callable = requests_from_findings


class UnusableResponse(Exception):
    pass


def chosen_chapters(workspace: Workspace, selection: Selection, grouped: dict) -> list[str]:
    wanted = sorted(grouped) if selection.everything \
        else sorted(set(selection.chapters) | set(selection.full_chapters))
    unknown = [chapter for chapter in wanted if chapter not in grouped]
    if unknown:
        raise SystemExit("unknown chapters: %s" % " ".join(unknown))
    explicit = workspace_module.explicit_chapters(workspace)
    skipped = [chapter for chapter in wanted if chapter in explicit]
    if skipped:
        print("skipping explicit-scene chapters: %s" % " ".join(skipped))
    return [chapter for chapter in wanted if chapter not in explicit]


def chapter_chunks(chapter: str, records: list[Record]) -> list[Chunk]:
    positions = [position for position, record in enumerate(records)
                 if mt.WORDS.search(record.jp)]
    return [Chunk("%s-%04d" % (chapter, start // CHUNK_RECORDS), chapter,
                  tuple(records[max(0, positions[start] - CONTEXT_RECORDS):positions[start]]),
                  tuple(records[position]
                        for position in positions[start:start + CHUNK_RECORDS]))
            for start in range(0, len(positions), CHUNK_RECORDS)]


def build_chunks(workspace: Workspace, selection: Selection) -> list[Chunk]:
    grouped = workspace_module.group_by_chapter(workspace_module.load_records(workspace))
    return [chunk for chapter in chosen_chapters(workspace, selection, grouped)
            for chunk in chapter_chunks(chapter, grouped[chapter])]


def custom_id(stage: Stage, request: StageRequest) -> str:
    return "%s-%s" % (stage.name, request.chunk.request_id)


def parameters(stage: Stage, shared_text: str, request: StageRequest) -> dict:
    return {"model": MODEL, "max_tokens": MAX_TOKENS,
            "output_config": {"effort": EFFORT,
                              "format": {"type": "json_schema", "schema": stage.schema}},
            "system": prompt.system_blocks(shared_text, stage.role),
            "messages": [{"role": "user",
                          "content": stage.user_message(stage.heading, request)}]}


def project(stage: Stage, shared_text: str, requests: list[StageRequest],
            batch: bool) -> ledger.Projection:
    return ledger.project(
        MODEL, batch, ledger.system_tokens(shared_text + stage.role), len(requests),
        sum(stage.projected_input_tokens(request) for request in requests),
        sum(stage.projected_output_tokens(request) for request in requests))


def parse_message(message: dict) -> dict:
    if message.get("stop_reason") != SUCCESSFUL_STOP:
        raise UnusableResponse("stop_reason %s" % message.get("stop_reason"))
    try:
        return json.loads(mt.text_of(message))
    except json.JSONDecodeError as error:
        raise UnusableResponse("bad json: %s" % error)


def store_message(workspace: Workspace, stage: Stage, request: StageRequest,
                  message: dict) -> Outcome:
    try:
        payload = parse_message(message)
    except UnusableResponse as error:
        return Outcome(0, 0, "RETRY %s" % error)
    return stage.store(workspace, request, payload)


def report_outcomes(outcomes: list[Outcome]) -> None:
    print("accepted %d, dropped %d over %d requests"
          % (sum(outcome.accepted for outcome in outcomes),
             sum(outcome.dropped for outcome in outcomes), len(outcomes)))


def handle_sync_message(workspace: Workspace, stage: Stage, request: StageRequest,
                        message: dict) -> Outcome:
    ledger.append_entry(workspace, LedgerEntry(stage.name, custom_id(stage, request), MODEL,
                                               False, message.get("usage", {})))
    outcome = store_message(workspace, stage, request, message)
    print(custom_id(stage, request), outcome.detail)
    return outcome


def run_sync(workspace: Workspace, stage: Stage, shared_text: str,
             requests: list[StageRequest], key: str, transport: Callable) -> None:
    def send(request: StageRequest) -> dict:
        return transport("POST", "/messages", parameters(stage, shared_text, request), key)

    outcomes = [handle_sync_message(workspace, stage, request, send(request))
                for request in requests[:1]]
    with ThreadPoolExecutor(SYNC_WORKERS) as pool:
        for request, message in zip(requests[1:], pool.map(send, requests[1:])):
            outcomes.append(handle_sync_message(workspace, stage, request, message))
    report_outcomes(outcomes)


def bookkeeping(batch_id: str, stage: Stage, selection: Selection,
                requests: list[StageRequest]) -> dict:
    return {"id": batch_id, "stage": stage.name, "chapters": list(selection.chapters),
            "all": selection.everything, "full": list(selection.full_chapters),
            "limit": selection.limit, **stage.bookkeeping_fields(requests)}


def submit_batch(workspace: Workspace, stage: Stage, shared_text: str, selection: Selection,
                 requests: list[StageRequest], key: str, transport: Callable) -> None:
    body = {"requests": [{"custom_id": custom_id(stage, request),
                          "params": parameters(stage, shared_text, request)}
                         for request in requests]}
    batch = transport("POST", "/messages/batches", body, key)
    workspace_module.append_json_line(
        workspace.batches_file, bookkeeping(batch["id"], stage, selection, requests))
    print("batch %s with %d requests: %s" % (batch["id"], len(requests),
                                             batch["processing_status"]))
    print("collect with: python -m tools.review %s collect %s" % (stage.name, batch["id"]))


def submit(workspace: Workspace, stage: Stage, selection: Selection, sync: bool, cap: float,
           transport: Callable = mt.call, load_key: Callable = mt.load_key) -> int:
    shared_text = prompt.shared_system_text(
        workspace, load_tables(workspace, SUMMARIZATION_RATIO))
    requests = stage.select_requests(workspace, selection)[:selection.limit or None]
    projection = project(stage, shared_text, requests, not sync)
    spent = ledger.spend(ledger.load_entries(workspace))
    print(ledger.describe_projection(projection, spent, cap))
    ledger.refuse_over_cap(spent, projection, cap)
    if not requests:
        print("nothing to send")
        return 0
    if sync:
        run_sync(workspace, stage, shared_text, requests, load_key(), transport)
    else:
        submit_batch(workspace, stage, shared_text, selection, requests, load_key(), transport)
    return 0


def find_bookkeeping(workspace: Workspace, stage: Stage, batch_id: str) -> dict:
    for entry in workspace_module.read_json_lines(workspace.batches_file):
        if entry["id"] == batch_id and entry["stage"] == stage.name:
            return entry
    raise SystemExit("batch %s is not a recorded %s batch in %s"
                     % (batch_id, stage.name, workspace.batches_file))


def handle_batch_result(workspace: Workspace, stage: Stage, batch_id: str,
                        request: StageRequest, result: dict, logged: set) -> Outcome:
    if result["type"] != BATCH_SUCCEEDED:
        return Outcome(0, 0, "RETRY %s" % result["type"])
    ledger_id = "%s/%s" % (batch_id, custom_id(stage, request))
    if ledger_id not in logged:
        ledger.append_entry(workspace, LedgerEntry(stage.name, ledger_id, MODEL, True,
                                                   result["message"].get("usage", {})))
    return store_message(workspace, stage, request, result["message"])


def collect(workspace: Workspace, stage: Stage, batch_id: str,
            transport: Callable = mt.call, load_key: Callable = mt.load_key) -> int:
    entry = find_bookkeeping(workspace, stage, batch_id)
    key = load_key()
    state = transport("GET", "/messages/batches/" + batch_id, key=key)
    print(state["processing_status"], state["request_counts"])
    if state["processing_status"] != BATCH_ENDED:
        return 0
    requests = {custom_id(stage, request): request
                for request in stage.restore_requests(workspace, entry).values()}
    logged = {logged_entry.request_id for logged_entry in ledger.load_entries(workspace)}
    outcomes = []
    results = transport("GET", "/messages/batches/%s/results" % batch_id, key=key, raw=True)
    for line in results.splitlines():
        answer = json.loads(line)
        if answer["custom_id"] in requests:
            outcome = handle_batch_result(workspace, stage, batch_id,
                                          requests[answer["custom_id"]], answer["result"],
                                          logged)
            print(answer["custom_id"], outcome.detail)
            outcomes.append(outcome)
    report_outcomes(outcomes)
    return 0
