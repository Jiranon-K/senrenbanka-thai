from __future__ import annotations

import json
import os

from .shapes import Record
from .tables import Tables
from .workspace import Workspace

NARRATION_LABEL = "(narration)"

REVIEWER_ROLE = """Role: Reviewer.
You check an existing Thai translation, line by line, against the Japanese original.
- Judge the Thai only against the Japanese (`jp`) of lines in this request. Never base a flag
  on the English (`en`), which localizes freely, or on lines that are not in the request. A
  Thai line that follows the Japanese where the English differs is correct.
- Decide first, then write. If your reasoning ends with the line being acceptable, emit no
  flag for it at all; `problem` never says a line is fine, arguably fine or a judgement call.
- Flag only real defects: content the Japanese lacks, omitted or summarized content, wrong
  meaning, wrong speaker gender (pronoun or particle against the character table), wrong
  kinship side, wrong address term or glossary term, a lost joke or pun, wrong register.
- A natural Thai particle, idiom or added subject pronoun is not an addition.
- Never flag a rendering that the rules above list as a project convention.
- Do not flag style preferences or wording you would merely have chosen differently. A
  correct line gets no flag, and an empty `flags` list is the normal answer.
- Every flag cites exactly one rule ID from the rules above in `rule`.
- `severity` is "major" only for wrong meaning, wrong speaker gender, wrong kinship side, a
  wrong name, or missing or invented content. Everything else, including pronoun choice and
  address style, is "minor".
- `problem` is at most 25 English words saying what is wrong and what the Japanese says. Do
  not write a corrected Thai line.
- Flag only idx from the lines to review, never an idx from the preceding context."""

ARBITER_ROLE = """Role: Arbiter.
Each line has the Japanese original (`jp`), its speaker, up to three preceding lines as
`context`, and two candidate Thai translations, `X` and `Y`. Choose the candidate that is
more faithful to the Japanese.
- Judge only against the Japanese and the rules, character table and glossary above. The
  order of X and Y is arbitrary and carries no information.
- Weigh these above fluency: wrong meaning, missing or invented content, speaker gender,
  kinship side, address terms and glossary terms.
- Answer "same" when neither candidate is meaningfully better, including when they differ
  only in style or in wording that is equally faithful.
- Never prefer a candidate for being longer or for following the Japanese word order more
  literally. A natural Thai particle, idiom or subject pronoun is not invented content.
- `context` is reference only; its Thai is not being judged.
- Return one choice per line with its `idx`, `better` as "X", "Y" or "same", and `reason`
  of at most 15 English words naming the deciding difference."""

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
