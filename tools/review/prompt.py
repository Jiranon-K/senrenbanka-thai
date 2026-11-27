from __future__ import annotations

import json
import os

from .shapes import Record
from .tables import Tables
from .workspace import Workspace

NARRATION_LABEL = "(narration)"

REVIEWER_ROLE = """Role: Reviewer.
You check an existing Thai translation, line by line, against the Japanese original.
- Judge the Thai only against the Japanese (`jp`). The English (`en`) is a reference that
  localizes freely: it must never be the reason for a flag, and a Thai line that follows the
  Japanese where the English differs is correct.
- Flag only real defects: content the Japanese lacks, omitted or summarized content, wrong
  meaning, wrong speaker gender (pronoun or particle against the character table), wrong
  kinship side, wrong address term or glossary term, a lost joke or pun, wrong register.
- Do not flag style preferences or wording you would merely have chosen differently. A
  correct line gets no flag, and an empty `flags` list is the normal answer.
- Every flag cites exactly one rule ID from the rules above in `rule`.
- `severity` is "major" when meaning, gender, kinship, a name or a term is wrong or content is
  missing or added, and "minor" otherwise.
- `problem` is at most 25 English words saying what is wrong and what the Japanese says. Do
  not write a corrected Thai line.
- Flag only idx from the lines to review, never an idx from the preceding context."""

REVISER_ROLE = """Role: Reviser.
You receive Thai lines with the Japanese original, and findings attached to some of them.
- Rewrite only the lines that carry `findings`. Return nothing for any other line.
- Translate from the Japanese (`jp`). The English (`en`) is a reference only and is never the
  source of wording or of content the Japanese lacks.
- Fix what the findings name and keep the parts of the line that are already correct, unless
  a finding asks for a full retranslation; then translate the whole line from the Japanese.
- Follow the rules, the character table and the glossary above.
- Keep the same opening and closing bracket as the Japanese line, leave no kana or kanji,
  drop ruby readings, and keep a literal backslash-n only where the Japanese has one.
- When a finding is mistaken and the current Thai is already right, return it unchanged.
- Return `idx` and `th` only, one entry per line that carries findings."""


class RulesFileMissing(Exception):
    pass


def read_rules(workspace: Workspace) -> str:
    if not os.path.isfile(workspace.rules_file):
        raise RulesFileMissing(
            "translation rules file not found: %s (write docs/TRANSLATION_RULES.md or point "
            "REVIEW_RULES_FILE at one)" % workspace.rules_file)
    with open(workspace.rules_file, encoding="utf-8-sig") as rules_file:
        return rules_file.read().strip()


def character_table(tables: Tables) -> str:
    rows = ["%s | %s | %s | %s | %s" % (profile.speaker, profile.sex, profile.self_pronoun,
                                        profile.polite_particle, profile.notes)
            for profile in tables.speakers.values() if profile.sex or profile.notes]
    return ("Characters (speaker | sex | Thai self pronoun | Thai polite particle | notes):\n"
            + "\n".join(rows))


def glossary_table(tables: Tables) -> str:
    rows = ["%s | %s | %s | %s | %s" % ("/".join(entry.jp_terms), entry.en, entry.th,
                                        entry.note, ";".join(entry.forbidden))
            for entry in tables.glossary]
    return "Glossary (jp | en | th | note | forbidden renderings):\n" + "\n".join(rows)


def shared_system_text(workspace: Workspace, tables: Tables) -> str:
    return "\n\n".join([read_rules(workspace), character_table(tables), glossary_table(tables)])


def system_blocks(shared_text: str, role: str) -> list[dict]:
    return [{"type": "text", "text": shared_text, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": role, "cache_control": {"type": "ephemeral"}}]


def line_fields(record: Record) -> dict:
    return {"idx": record.idx, "speaker": record.speaker or NARRATION_LABEL,
            "jp": record.jp, "en": record.en, "th": record.th}


def line_fields_with_findings(record: Record, findings: tuple) -> dict:
    own = [{"rule": found.rule, "problem": found.problem}
           for found in findings if found.idx == record.idx]
    return {**line_fields(record), "findings": own} if own else line_fields(record)


def user_message(heading: str, context: tuple, records: tuple, findings: tuple) -> str:
    return ("Preceding context (reference only):\n"
            + json.dumps([line_fields(record) for record in context], ensure_ascii=False)
            + "\n\n" + heading + "\n"
            + json.dumps([line_fields_with_findings(record, findings) for record in records],
                         ensure_ascii=False))
