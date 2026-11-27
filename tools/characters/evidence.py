from __future__ import annotations

import argparse
import collections
import csv
import json
import operator
import os
import re
import sys
import urllib.request
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import paths
import scenario

csv.field_size_limit(10 ** 9)

VNDB_VN_ENDPOINT = "https://api.vndb.org/kana/vn"
VNDB_CHARACTER_ENDPOINT = "https://api.vndb.org/kana/character"
VNDB_SEARCH_TITLE = "Senren Banka"
VNDB_ORIGINAL_RELEASE_YEAR = "2016"
VNDB_CACHE = os.path.join(paths.WORK, "mt", "vndb_characters.json")
CHARACTERS_CSV = os.path.join(paths.WORK, "characters.csv")

TRADITIONAL_CHINESE = 3

MALE = "male"
FEMALE = "female"
MIXED = "mixed"
DISPUTED = "disputed"
SEX_BY_VNDB_CODE = {"m": MALE, "f": FEMALE, "b": "both", "n": "sexless"}

LOCKED = "locked"
PROVISIONAL = "provisional"
UNKNOWN = "unknown"
CONFLICT = "CONFLICT"
EVIDENCE_LEVELS = (LOCKED, PROVISIONAL, UNKNOWN, CONFLICT)

MALE_PRONOUNS = frozenset({"俺", "オレ", "僕", "ボク"})
FEMALE_PRONOUNS = frozenset({"あたし", "アタシ", "わたくし"})
PRONOUN_PATTERN = re.compile(
    "わたくし|あたし|わたし"
    "|(?<![ァ-ヶー])(?:アタシ|オレ|ボク)(?![ァ-ヶー])"
    "|俺|(?<![下公])僕|私|自分|吾輩"
)
MINIMUM_GENDERED_HITS = 5
MINIMUM_GENDERED_SHARE = 0.3
MINIMUM_GENDERED_AGREEMENT = 0.8

FEMALE_LABEL_WORDS = ("女", "母", "姉", "妹", "娘", "婆", "ママ")
MALE_LABEL_WORDS = ("男", "父", "兄", "弟", "爺", "おじさん", "おじいさん",
                    "オッサン", "オヤジ", "オッチャン", "パパ")

SHARED_LABEL_SEPARATORS = ("/", "＆", "・")
LABEL_PART_PATTERN = re.compile("[/＆・]")
LABEL_SUFFIX_PATTERN = re.compile("(?:の声|？)+$")
NAME_TOKEN_PATTERN = re.compile(r"[\s・＝=]+")

HAND_MAINTAINED_COLUMNS = ("thai_self_pronoun", "thai_polite_particle", "notes")
COLUMNS = ("speaker_en", "jp_label", "cn_label", "lines", "vndb_name",
           "vndb_original", "vndb_role", "sex_vndb", "sex_ingame", "sex",
           "evidence") + HAND_MAINTAINED_COLUMNS


@dataclass(frozen=True)
class VndbCharacter:
    identifier: str
    name: str
    original: str
    sex: str
    age: str
    role: str


@dataclass(frozen=True)
class BlockLabels:
    japanese_text: str
    japanese_label: str
    voice_owner: str
    chinese_label: str


@dataclass(frozen=True)
class SpokenLine:
    speaker_en: str
    japanese_text: str
    japanese_label: str
    voice_owner: str
    chinese_label: str


@dataclass(frozen=True)
class PronounCounts:
    male: int = 0
    female: int = 0
    neutral: int = 0

    def __add__(self, other: PronounCounts) -> PronounCounts:
        return PronounCounts(self.male + other.male, self.female + other.female,
                             self.neutral + other.neutral)


@dataclass(frozen=True)
class SpeakerEvidence:
    speaker_en: str
    lines: int
    japanese_label: str
    chinese_label: str
    voice_owner: str
    pronouns: PronounCounts


@dataclass(frozen=True)
class HandMaintained:
    thai_self_pronoun: str = ""
    thai_polite_particle: str = ""
    notes: str = ""


@dataclass(frozen=True)
class Verdict:
    sex_ingame: str
    sex: str
    evidence: str


@dataclass(frozen=True)
class CharacterRow:
    speaker_en: str
    jp_label: str
    cn_label: str
    lines: int
    vndb_name: str
    vndb_original: str
    vndb_role: str
    sex_vndb: str
    sex_ingame: str
    sex: str
    evidence: str
    thai_self_pronoun: str
    thai_polite_particle: str
    notes: str


def post_json(url: str, body: dict) -> dict:
    request = urllib.request.Request(
        url, json.dumps(body).encode("utf-8"), {"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def original_release_id(search_response: dict) -> str:
    originals = [result for result in search_response["results"]
                 if (result.get("released") or "").startswith(VNDB_ORIGINAL_RELEASE_YEAR)]
    if not originals:
        raise SystemExit("VNDB search returned no %s release for %r"
                         % (VNDB_ORIGINAL_RELEASE_YEAR, VNDB_SEARCH_TITLE))
    return min(originals, key=operator.itemgetter("released"))["id"]


def fetch_character_pages(vn_id: str) -> list[dict]:
    pages = []
    more = True
    while more:
        page = post_json(VNDB_CHARACTER_ENDPOINT, {
            "filters": ["vn", "=", ["id", "=", vn_id]],
            "fields": "name,original,sex,age,vns.role,vns.id",
            "results": 100,
            "page": len(pages) + 1,
        })
        pages.append(page)
        more = bool(page.get("more"))
    return pages


def fetch_vndb_payload() -> dict:
    search_response = post_json(VNDB_VN_ENDPOINT, {
        "filters": ["search", "=", VNDB_SEARCH_TITLE],
        "fields": "title,alttitle,released",
    })
    vn_id = original_release_id(search_response)
    return {"vn_id": vn_id, "vn_search": search_response,
            "character_pages": fetch_character_pages(vn_id)}


def load_vndb_payload(cache_path: str, refresh: bool, fetch=fetch_vndb_payload) -> dict:
    if not refresh and os.path.exists(cache_path):
        with open(cache_path, encoding="utf-8") as cache_file:
            return json.load(cache_file)
    payload = fetch()
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as cache_file:
        json.dump(payload, cache_file, ensure_ascii=False, indent=1)
    return payload


def role_in_vn(record: dict, vn_id: str) -> str:
    roles = [appearance.get("role") or "" for appearance in record.get("vns") or []
             if appearance.get("id") == vn_id]
    return roles[0] if roles else ""


def parse_vndb_characters(payload: dict) -> list[VndbCharacter]:
    vn_id = payload["vn_id"]
    return [
        VndbCharacter(
            identifier=record["id"],
            name=record.get("name") or "",
            original=record.get("original") or "",
            sex=SEX_BY_VNDB_CODE.get((record.get("sex") or [None])[0], ""),
            age="" if record.get("age") is None else str(record["age"]),
            role=role_in_vn(record, vn_id),
        )
        for page in payload["character_pages"]
        for record in page["results"]
    ]


def dialogue_entries(node):
    if isinstance(node, list):
        if (len(node) >= 3 and scenario.ALL_AGES.is_block(node[2])
                and (node[0] is None or isinstance(node[0], str))):
            yield node
        for element in node:
            yield from dialogue_entries(element)
    elif isinstance(node, dict):
        for value in node.values():
            yield from dialogue_entries(value)


def chinese_label_of(block: list) -> str:
    simplified = block[scenario.CN][0] or ""
    if simplified and simplified != (block[scenario.EN][0] or ""):
        return simplified
    return block[TRADITIONAL_CHINESE][0] or ""


def is_control_block(block: list) -> bool:
    japanese_label = block[scenario.JP][0]
    return japanese_label is not None and japanese_label == block[scenario.EN][0]


def labels_of_entry(entry: list) -> BlockLabels | None:
    block = entry[2]
    if is_control_block(block):
        return None
    voice_owner = entry[0] or ""
    return BlockLabels(
        japanese_text=block[scenario.JP][1],
        japanese_label=block[scenario.JP][0] or voice_owner,
        voice_owner=voice_owner,
        chinese_label=chinese_label_of(block),
    )


def block_labels(parsed_scenario) -> list[BlockLabels | None]:
    entry_by_block = {id(entry[2]): entry for entry in dialogue_entries(parsed_scenario)}
    return [
        labels_of_entry(entry_by_block[id(block)]) if id(block) in entry_by_block else None
        for block in scenario.ALL_AGES.blocks(parsed_scenario)
    ]


def read_block_labels(scenario_path: str) -> list[BlockLabels | None]:
    with open(scenario_path, encoding="utf-8") as scenario_file:
        return block_labels(json.load(scenario_file))


def read_speaker_rows(strings_path: str) -> dict[str, list[dict]]:
    rows_by_file = collections.defaultdict(list)
    with open(strings_path, encoding="utf-8-sig", newline="") as strings_file:
        for row in csv.DictReader(strings_file):
            if row["speaker_en"] and row["idx"].isdigit():
                rows_by_file[row["file"]].append(row)
    return rows_by_file


def spoken_line(row: dict, labels: BlockLabels) -> SpokenLine:
    if labels.japanese_text != row["jp"]:
        raise SystemExit("%s idx %s: strings CSV and scenario JSON disagree; re-export first"
                         % (row["file"], row["idx"]))
    return SpokenLine(row["speaker_en"], row["jp"], labels.japanese_label,
                      labels.voice_owner, labels.chinese_label)


def read_spoken_lines(strings_path: str, scenario_directory: str) -> list[SpokenLine]:
    lines = []
    for file_name, rows in read_speaker_rows(strings_path).items():
        labels_by_index = read_block_labels(os.path.join(scenario_directory, file_name))
        for row in rows:
            labels = labels_by_index[int(row["idx"])]
            if labels is not None:
                lines.append(spoken_line(row, labels))
    return lines


def count_pronouns(japanese_text: str) -> PronounCounts:
    hits = PRONOUN_PATTERN.findall(japanese_text)
    male = sum(1 for hit in hits if hit in MALE_PRONOUNS)
    female = sum(1 for hit in hits if hit in FEMALE_PRONOUNS)
    return PronounCounts(male, female, len(hits) - male - female)


def pronoun_sex(counts: PronounCounts) -> str:
    gendered = counts.male + counts.female
    if gendered < MINIMUM_GENDERED_HITS:
        return ""
    if gendered / (gendered + counts.neutral) < MINIMUM_GENDERED_SHARE:
        return ""
    if counts.male / gendered >= MINIMUM_GENDERED_AGREEMENT:
        return MALE
    if counts.female / gendered >= MINIMUM_GENDERED_AGREEMENT:
        return FEMALE
    return ""


def label_word_sex(japanese_label: str) -> str:
    has_female_word = any(word in japanese_label for word in FEMALE_LABEL_WORDS)
    has_male_word = any(word in japanese_label for word in MALE_LABEL_WORDS)
    if has_female_word == has_male_word:
        return ""
    return FEMALE if has_female_word else MALE


def is_shared_label(japanese_label: str) -> bool:
    return any(separator in japanese_label for separator in SHARED_LABEL_SEPARATORS)


def most_common(values) -> str:
    counted = collections.Counter(value for value in values if value)
    return counted.most_common(1)[0][0] if counted else ""


def sole_value(values) -> str:
    distinct = set(values)
    return distinct.pop() if len(distinct) == 1 else ""


def speaker_evidence(speaker_en: str, lines: list[SpokenLine]) -> SpeakerEvidence:
    own_lines = [line for line in lines if not is_shared_label(line.japanese_label)]
    return SpeakerEvidence(
        speaker_en=speaker_en,
        lines=len(lines),
        japanese_label=most_common(line.japanese_label for line in lines),
        chinese_label=most_common(line.chinese_label for line in lines),
        voice_owner=sole_value(line.voice_owner for line in lines),
        pronouns=sum((count_pronouns(line.japanese_text) for line in own_lines),
                     PronounCounts()),
    )


def summarise_speakers(lines: list[SpokenLine]) -> list[SpeakerEvidence]:
    lines_by_speaker = collections.defaultdict(list)
    for line in lines:
        lines_by_speaker[line.speaker_en].append(line)
    return [speaker_evidence(speaker_en, speaker_lines)
            for speaker_en, speaker_lines in lines_by_speaker.items()]


def name_keys(original: str) -> set[str]:
    tokens = [token for token in NAME_TOKEN_PATTERN.split(original) if token]
    return set(tokens) | {"".join(tokens)}


def label_parts(japanese_label: str) -> list[str]:
    parts = [LABEL_SUFFIX_PATTERN.sub("", part.strip())
             for part in LABEL_PART_PATTERN.split(japanese_label)]
    return [part for part in parts if part]


def character_named(japanese_name: str, characters: list[VndbCharacter]) -> VndbCharacter | None:
    matches = [character for character in characters
               if character.original and japanese_name in name_keys(character.original)]
    return matches[0] if len(matches) == 1 else None


def characters_behind(speaker: SpeakerEvidence,
                      characters: list[VndbCharacter]) -> list[VndbCharacter]:
    parts = label_parts(speaker.japanese_label)
    candidates = [character_named(part, characters) for part in parts]
    matched = [character for character in candidates if character is not None]
    if len(parts) > 1:
        return matched if len(matched) == len(parts) else []
    if matched or not speaker.voice_owner:
        return matched
    voice_character = character_named(speaker.voice_owner, characters)
    return [] if voice_character is None else [voice_character]


def combined_sex(sexes: list[str]) -> str:
    distinct = {sex for sex in sexes if sex}
    if len(distinct) > 1:
        return MIXED
    return distinct.pop() if distinct else ""


def joined(values: list[str]) -> str:
    return " + ".join(dict.fromkeys(value for value in values if value))


def decide(sex_vndb: str, sex_label: str, sex_pronoun: str) -> Verdict:
    ingame_signals = {sex for sex in (sex_label, sex_pronoun) if sex}
    sex_ingame = DISPUTED if len(ingame_signals) > 1 else "".join(ingame_signals)
    signals = ingame_signals | ({sex_vndb} if sex_vndb else set())
    if len(signals) > 1:
        return Verdict(sex_ingame, "", CONFLICT)
    if sex_vndb:
        return Verdict(sex_ingame, sex_vndb, LOCKED)
    if sex_ingame:
        return Verdict(sex_ingame, sex_ingame, PROVISIONAL)
    return Verdict("", "", UNKNOWN)


def character_row(speaker: SpeakerEvidence, characters: list[VndbCharacter],
                  hand_maintained: HandMaintained) -> CharacterRow:
    matched = characters_behind(speaker, characters)
    sex_vndb = combined_sex([character.sex for character in matched])
    verdict = decide(sex_vndb, label_word_sex(speaker.japanese_label),
                     pronoun_sex(speaker.pronouns))
    return CharacterRow(
        speaker_en=speaker.speaker_en,
        jp_label=speaker.japanese_label,
        cn_label=speaker.chinese_label,
        lines=speaker.lines,
        vndb_name=joined([character.name for character in matched]),
        vndb_original=joined([character.original for character in matched]),
        vndb_role=joined([character.role for character in matched]),
        sex_vndb=sex_vndb,
        sex_ingame=verdict.sex_ingame,
        sex=verdict.sex,
        evidence=verdict.evidence,
        thai_self_pronoun=hand_maintained.thai_self_pronoun,
        thai_polite_particle=hand_maintained.thai_polite_particle,
        notes=hand_maintained.notes,
    )


def merge(speakers: list[SpeakerEvidence], characters: list[VndbCharacter],
          hand_maintained: dict[str, HandMaintained]) -> list[CharacterRow]:
    rows = [character_row(speaker, characters,
                          hand_maintained.get(speaker.speaker_en, HandMaintained()))
            for speaker in speakers]
    return sorted(rows, key=lambda row: (-row.lines, row.speaker_en))


def read_hand_maintained(characters_path: str) -> dict[str, HandMaintained]:
    if not os.path.exists(characters_path):
        return {}
    with open(characters_path, encoding="utf-8-sig", newline="") as characters_file:
        return {
            row["speaker_en"]: HandMaintained(
                **{column: row.get(column) or "" for column in HAND_MAINTAINED_COLUMNS})
            for row in csv.DictReader(characters_file)
        }


def write_rows(characters_path: str, rows: list[CharacterRow]) -> None:
    with open(characters_path, "w", encoding="utf-8-sig", newline="") as characters_file:
        writer = csv.writer(characters_file)
        writer.writerow(COLUMNS)
        for row in rows:
            writer.writerow([getattr(row, column) for column in COLUMNS])


def coverage_lines(rows: list[CharacterRow]) -> list[str]:
    total_lines = sum(row.lines for row in rows) or 1
    report = []
    for level in EVIDENCE_LEVELS:
        level_rows = [row for row in rows if row.evidence == level]
        level_lines = sum(row.lines for row in level_rows)
        report.append("%-11s %3d speakers  %6d lines  %5.1f%%"
                      % (level, len(level_rows), level_lines, 100 * level_lines / total_lines))
    return report


def conflict_lines(rows: list[CharacterRow]) -> list[str]:
    return ["CONFLICT %s (%s): vndb=%s ingame=%s lines=%d"
            % (row.speaker_en, row.jp_label, row.sex_vndb or "-", row.sex_ingame or "-", row.lines)
            for row in rows if row.evidence == CONFLICT]


def parse_arguments(arguments: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="evidence")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--strings", default=paths.CSV_CN)
    parser.add_argument("--scenarios", default=paths.JSON_CN)
    parser.add_argument("--cache", default=VNDB_CACHE)
    parser.add_argument("--output", default=CHARACTERS_CSV)
    return parser.parse_args(arguments)


def main(arguments: list[str]) -> int:
    options = parse_arguments(arguments)
    characters = parse_vndb_characters(load_vndb_payload(options.cache, options.refresh))
    speakers = summarise_speakers(read_spoken_lines(options.strings, options.scenarios))
    rows = merge(speakers, characters, read_hand_maintained(options.output))
    write_rows(options.output, rows)
    conflicts = conflict_lines(rows)
    print("\n".join(coverage_lines(rows) + conflicts))
    print("wrote %d speakers -> %s" % (len(rows), options.output))
    return 1 if conflicts else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
