from __future__ import annotations

import csv
import json
import os

from .shapes import Record
from .tables import GlossaryEntry, SpeakerProfile, Tables
from .workspace import Workspace

STRINGS_COLUMNS = ("file", "idx", "speaker_en", "jp", "en", "th")
CHARACTER_COLUMNS = ("speaker_en", "sex", "thai_self_pronoun", "thai_polite_particle", "notes")
GLOSSARY_COLUMNS = ("en", "jp", "th", "note", "forbidden")
CHAPTER = "900"
SCENARIO_FILE = "900・synthetic.ks.json"
RULES_TEXT = "X1 Synthetic rule: translate from the Japanese."

SPEAKERS = {
    "Masaomi": SpeakerProfile("Masaomi", "male", "ผม", "ครับ", ""),
    "Yoshino": SpeakerProfile("Yoshino", "female", "ฉัน", "ค่ะ", ""),
    "Rentarou": SpeakerProfile("Rentarou", "male", "", "", ""),
    "Koharu": SpeakerProfile("Koharu", "female", "", "", ""),
    "Beast": SpeakerProfile("Beast", "", "", "", ""),
}
GLOSSARY = (
    GlossaryEntry("miko", ("巫女",), "มิโกะ", "", ()),
    GlossaryEntry("Shrine Princess", ("巫女姫",), "องค์หญิงมิโกะ", "", ()),
    GlossaryEntry("Rentarou", ("廉太郎",), "เร็นทาโร่", "", ("เรนทาโร่", "เร็นทาโร")),
    GlossaryEntry("exorcist", ("陰陽師", "祓い屋"), "นักปราบผี", "", ()),
    GlossaryEntry("ayakashi", (), "อายากาชิ", "", ()),
)
TABLES = Tables(SPEAKERS, GLOSSARY, 1.0)


def record(th: str, jp: str = "「これは試験です」", speaker: str = "Yoshino",
           idx: str = "1") -> Record:
    return Record(CHAPTER, idx, speaker, jp, "This is a test.", th)


def write_csv(path: str, columns: tuple, rows: list[dict], encoding: str) -> None:
    with open(path, "w", encoding=encoding, newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(columns))
        writer.writeheader()
        writer.writerows(rows)


def strings_row(source: Record) -> dict:
    return {"file": SCENARIO_FILE, "idx": source.idx, "speaker_en": source.speaker,
            "jp": source.jp, "en": source.en, "th": source.th}


def build_workspace(directory: str, records: list[Record], thai_newline: str = "\r\n",
                    with_rules: bool = True) -> Workspace:
    workspace = Workspace(
        strings_csv=os.path.join(directory, "strings_cn.csv"),
        thai_directory=os.path.join(directory, "th"),
        characters_csv=os.path.join(directory, "characters.csv"),
        glossary_csv=os.path.join(directory, "glossary.csv"),
        scenarios_json=os.path.join(directory, "scenarios.json"),
        rules_file=os.path.join(directory, "rules.md"),
        review_directory=os.path.join(directory, "mt", "review"))
    os.makedirs(workspace.thai_directory)
    control = {"file": SCENARIO_FILE, "idx": "0", "speaker_en": "face", "jp": "control",
               "en": "", "th": ""}
    write_csv(workspace.strings_csv, STRINGS_COLUMNS,
              [control] + [strings_row(source) for source in records], "utf-8-sig")
    write_csv(workspace.characters_csv, CHARACTER_COLUMNS,
              [{"speaker_en": profile.speaker, "sex": profile.sex,
                "thai_self_pronoun": profile.self_pronoun,
                "thai_polite_particle": profile.polite_particle, "notes": profile.notes}
               for profile in SPEAKERS.values()], "utf-8-sig")
    write_csv(workspace.glossary_csv, GLOSSARY_COLUMNS,
              [{"en": entry.en, "jp": "/".join(entry.jp_terms) or "妖", "th": entry.th,
                "note": entry.note, "forbidden": ";".join(entry.forbidden)}
               for entry in GLOSSARY], "utf-8")
    with open(workspace.scenarios_json, "w", encoding="utf-8") as scenarios_file:
        json.dump([{"file": SCENARIO_FILE, "is_h": False}], scenarios_file)
    with open(workspace.thai_file(CHAPTER), "w", encoding="utf-8", newline="") as thai_file:
        thai_file.write("".join("%s\t%s%s" % (source.idx, source.th, thai_newline)
                                for source in records if source.th))
    if with_rules:
        with open(workspace.rules_file, "w", encoding="utf-8") as rules_file:
            rules_file.write(RULES_TEXT)
    return workspace
