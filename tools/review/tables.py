from __future__ import annotations

import csv
from dataclasses import dataclass

from .workspace import Workspace

NARRATOR = "Masaomi"
MALE = "male"
FEMALE = "female"
MINIMUM_TERM_LENGTH = 2


@dataclass(frozen=True)
class SpeakerProfile:
    speaker: str
    sex: str
    self_pronoun: str
    polite_particle: str
    notes: str


@dataclass(frozen=True)
class GlossaryEntry:
    en: str
    jp_terms: tuple
    th: str
    note: str
    forbidden: tuple


@dataclass(frozen=True)
class Tables:
    speakers: dict
    glossary: tuple
    summarization_ratio: float

    def sex_of(self, speaker: str) -> str:
        profile = self.speakers.get(speaker or NARRATOR)
        return profile.sex if profile else ""


def load_speakers(path: str) -> dict[str, SpeakerProfile]:
    with open(path, encoding="utf-8-sig", newline="") as characters_file:
        return {row["speaker_en"]: SpeakerProfile(
                    row["speaker_en"], row["sex"].strip(), row["thai_self_pronoun"].strip(),
                    row["thai_polite_particle"].strip(), row["notes"].strip())
                for row in csv.DictReader(characters_file)}


def load_glossary(path: str) -> tuple[GlossaryEntry, ...]:
    with open(path, encoding="utf-8-sig", newline="") as glossary_file:
        return tuple(GlossaryEntry(
                         row["en"],
                         tuple(term.strip() for term in row["jp"].split("/")
                               if len(term.strip()) >= MINIMUM_TERM_LENGTH),
                         row["th"].strip(), row["note"],
                         tuple(wrong.strip() for wrong in (row.get("forbidden") or "").split(";")
                               if wrong.strip()))
                     for row in csv.DictReader(glossary_file))


def load_tables(workspace: Workspace, summarization_ratio: float) -> Tables:
    return Tables(load_speakers(workspace.characters_csv),
                  load_glossary(workspace.glossary_csv), summarization_ratio)
