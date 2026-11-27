from __future__ import annotations

import csv
import dataclasses
import json
import os
import sys
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mt
import paths
import tsv

from .shapes import Finding, Record, Revision, revision_from_fields

csv.field_size_limit(10 ** 9)

RULES_FILE_VARIABLE = "REVIEW_RULES_FILE"
DEFAULT_RULES_FILE = os.path.join(paths.REPO, "docs", "TRANSLATION_RULES.md")


@dataclass(frozen=True)
class Workspace:
    strings_csv: str
    thai_directory: str
    characters_csv: str
    glossary_csv: str
    scenarios_json: str
    rules_file: str
    review_directory: str

    @property
    def lint_file(self) -> str:
        return os.path.join(self.review_directory, "lint.json")

    @property
    def changes_file(self) -> str:
        return os.path.join(self.review_directory, "changes.jsonl")

    @property
    def report_file(self) -> str:
        return os.path.join(self.review_directory, "before_after.html")

    @property
    def ledger_file(self) -> str:
        return os.path.join(self.review_directory, "ledger.jsonl")

    @property
    def batches_file(self) -> str:
        return os.path.join(self.review_directory, "batches.jsonl")

    @property
    def rejected_file(self) -> str:
        return os.path.join(self.review_directory, "rejected.jsonl")

    def flags_file(self, chapter: str) -> str:
        return os.path.join(self.review_directory, "flags", chapter + ".json")

    def revised_file(self, chapter: str) -> str:
        return os.path.join(self.review_directory, "revised", chapter + ".json")

    def thai_file(self, chapter: str) -> str:
        return os.path.join(self.thai_directory, chapter + ".tsv")


def repository_workspace() -> Workspace:
    return Workspace(
        strings_csv=paths.CSV_CN,
        thai_directory=paths.TH_DIR,
        characters_csv=os.path.join(paths.WORK, "characters.csv"),
        glossary_csv=paths.GLOSSARY,
        scenarios_json=paths.SCENARIOS,
        rules_file=os.environ.get(RULES_FILE_VARIABLE, DEFAULT_RULES_FILE),
        review_directory=os.path.join(paths.WORK, "mt", "review"))


def load_records(workspace: Workspace) -> list[Record]:
    with open(workspace.strings_csv, encoding="utf-8-sig", newline="") as strings_file:
        return [Record(tsv.prefix(row["file"]), row["idx"], row["speaker_en"],
                       row["jp"], row["en"], row["th"])
                for row in csv.DictReader(strings_file) if not mt.is_marker(row)]


def group_by_chapter(records: list[Record]) -> dict[str, list[Record]]:
    grouped: dict[str, list[Record]] = {}
    for record in records:
        grouped.setdefault(record.chapter, []).append(record)
    return grouped


def explicit_chapters(workspace: Workspace) -> set[str]:
    with open(workspace.scenarios_json, encoding="utf-8") as scenarios_file:
        return {tsv.prefix(entry["file"]) for entry in json.load(scenarios_file)
                if entry.get("is_h")}


def read_json_lines(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as lines_file:
        return [json.loads(line) for line in lines_file if line.strip()]


def append_json_line(path: str, fields: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as lines_file:
        lines_file.write(json.dumps(fields, ensure_ascii=False) + "\n")


def write_shapes(path: str, shapes: list) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as shapes_file:
        json.dump([dataclasses.asdict(shape) for shape in shapes], shapes_file,
                  ensure_ascii=False, indent=1)


def read_fields(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as shapes_file:
        return json.load(shapes_file)


def read_findings(path: str) -> list[Finding]:
    return [Finding(**fields) for fields in read_fields(path)]


def read_revisions(path: str) -> list[Revision]:
    return [revision_from_fields(fields) for fields in read_fields(path)]
