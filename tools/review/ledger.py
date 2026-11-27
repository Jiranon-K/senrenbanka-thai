from __future__ import annotations

import collections
from dataclasses import dataclass

from . import workspace as workspace_module
from .shapes import LedgerEntry
from .workspace import Workspace

DEFAULT_CAP_USD = 40.0
BATCH_PRICE_FACTOR = 0.5
TOKENS_PER_PRICE_UNIT = 1_000_000

INPUT_TOKENS_PER_RECORD = 125
THAI_TOKENS_PER_RECORD = 61
REVIEWER_OUTPUT_TOKENS_PER_RECORD = 40
TOKENS_PER_FINDING = 40
SYSTEM_CHARACTERS_PER_TOKEN = 2.0


@dataclass(frozen=True)
class Price:
    input: float
    output: float
    cache_write: float
    cache_read: float


PRICES = {"claude-sonnet-5-5": Price(input=2.00, output=10.00, cache_write=2.50, cache_read=0.10)}


@dataclass(frozen=True)
class Projection:
    requests: int
    input_tokens: int
    cache_write_tokens: int
    cache_read_tokens: int
    output_tokens: int
    usd: float


class CapExceeded(Exception):
    pass


def usage_cost(model: str, batch: bool, usage: dict) -> float:
    price = PRICES[model]
    full_price = (usage.get("input_tokens", 0) * price.input
                  + usage.get("cache_creation_input_tokens", 0) * price.cache_write
                  + usage.get("cache_read_input_tokens", 0) * price.cache_read
                  + usage.get("output_tokens", 0) * price.output) / TOKENS_PER_PRICE_UNIT
    return full_price * BATCH_PRICE_FACTOR if batch else full_price


def entry_cost(entry: LedgerEntry) -> float:
    return usage_cost(entry.model, entry.batch, entry.usage)


def load_entries(workspace: Workspace) -> list[LedgerEntry]:
    return [LedgerEntry(**fields)
            for fields in workspace_module.read_json_lines(workspace.ledger_file)]


def append_entry(workspace: Workspace, entry: LedgerEntry) -> None:
    workspace_module.append_json_line(workspace.ledger_file, {
        "stage": entry.stage, "request_id": entry.request_id, "model": entry.model,
        "batch": entry.batch, "usage": entry.usage})


def spend(entries: list[LedgerEntry]) -> float:
    return sum(entry_cost(entry) for entry in entries)


def system_tokens(system_text: str) -> int:
    return round(len(system_text) / SYSTEM_CHARACTERS_PER_TOKEN)


def project(model: str, batch: bool, system_token_count: int, requests: int,
            input_tokens: int, output_tokens: int) -> Projection:
    cache_write_tokens = system_token_count if requests else 0
    cache_read_tokens = system_token_count * max(requests - 1, 0)
    usd = usage_cost(model, batch, {
        "input_tokens": input_tokens,
        "cache_creation_input_tokens": cache_write_tokens,
        "cache_read_input_tokens": cache_read_tokens,
        "output_tokens": output_tokens})
    return Projection(requests, input_tokens, cache_write_tokens, cache_read_tokens,
                      output_tokens, usd)


def describe_projection(projection: Projection, spent: float, cap: float) -> str:
    return ("projection: %d requests, input %d, cache write %d, cache read %d, output %d "
            "tokens = $%.4f; ledger spend $%.4f; cap $%.2f"
            % (projection.requests, projection.input_tokens, projection.cache_write_tokens,
               projection.cache_read_tokens, projection.output_tokens, projection.usd,
               spent, cap))


def refuse_over_cap(spent: float, projection: Projection, cap: float) -> None:
    if spent + projection.usd > cap:
        raise CapExceeded("refusing to submit: ledger spend $%.4f plus projection $%.4f "
                          "exceeds the cap $%.2f" % (spent, projection.usd, cap))


def thinking_tokens(usage: dict) -> int:
    return (usage.get("output_tokens_details") or {}).get("thinking_tokens", 0)


def stage_summary(entries: list[LedgerEntry]) -> list[str]:
    by_stage: dict[str, list[LedgerEntry]] = collections.defaultdict(list)
    for entry in entries:
        by_stage[entry.stage].append(entry)
    return ["%s: %d requests, input %d, cache write %d, cache read %d, output %d "
            "(thinking %d) tokens, $%.4f"
            % (stage, len(stage_entries),
               sum(entry.usage.get("input_tokens", 0) for entry in stage_entries),
               sum(entry.usage.get("cache_creation_input_tokens", 0) for entry in stage_entries),
               sum(entry.usage.get("cache_read_input_tokens", 0) for entry in stage_entries),
               sum(entry.usage.get("output_tokens", 0) for entry in stage_entries),
               sum(thinking_tokens(entry.usage) for entry in stage_entries),
               spend(stage_entries))
            for stage, stage_entries in sorted(by_stage.items())]


def run(workspace: Workspace) -> int:
    entries = load_entries(workspace)
    for line in stage_summary(entries):
        print(line)
    print("total $%.4f of default cap $%.2f" % (spend(entries), DEFAULT_CAP_USD))
    return 0
