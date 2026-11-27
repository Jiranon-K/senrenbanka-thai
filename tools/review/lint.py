from __future__ import annotations

import collections
import re

from . import workspace as workspace_module
from .shapes import LINT, MAJOR, MINOR, Finding, Record
from .tables import FEMALE, MALE, GlossaryEntry, Tables, load_tables
from .workspace import Workspace, mt

SUMMARIZATION_RATIO = 1.15
SUMMARIZATION_MINIMUM_JAPANESE = 25

MALE_PARTICLE = "ครับ"
MALE_PRONOUN = "ผม"
FEMALE_MARKERS = ("นะคะ", "ค่ะ", "ดิฉัน")
HAIR_IN_JAPANESE = ("髪", "ヘア")
HAIR_PREFIXES = ("ทรง", "เส้น", "สระ", "หวี", "ปอย", "ตัด", "มัด", "ถัก", "เกล้า", "ย้อม",
                 "เป่า", "ลูบ", "ปัด", "เรือน", "รวบ", "ไว้", "ปล่อย", "ขน", "หัว", "เผ้า",
                 "กิ๊บติด", "ยางรัด", "ที่คาด", "ปิ่นปัก", "หนีบ", "สาง", "จัด", "แสก", "วิก",
                 "ช่อ", "กระจุก", "ดึง", "ขยี้", "ทัด", "เสย", "เซ็ต", "ทำ", "ขยุ้ม")
HAIR_SUFFIXES = ("ยาว", "สั้น", "สี", "หางม้า", "เปีย", "ดำ", "ทอง", "ขาว", "เงิน", "หยิก",
                 "เผ้า", "หงอก", "ร่วง", "เปียก", "ยุ่ง", "ชี้", "ม้า", "บ๊อบ", "ทวิน", "หน้าม้า",
                 "ของเธอ", "ของเขา", "สลวย", "นุ่ม", "ปลิว", "สยาย", "ที่ยาว", "ที่เปียก",
                 "แกละ", "จุก", "ปลอม", "ด้านหลัง", "ข้าง")
MALE_PRONOUN_PATTERN = re.compile(
    "".join("(?<!%s)" % prefix for prefix in HAIR_PREFIXES)
    + MALE_PRONOUN + "(?!%s)" % "|".join(HAIR_SUFFIXES))
OUTER_BRACKETS = {"「": "」", "『": "』", "（": "）", "(": ")"}
INNER_QUOTATION = re.compile("『[^』]*』|“[^”]*”|「[^」]*」|‘[^’]*’|\"[^\"]*\"|'[^']*'")

GRANDFATHER_IN_JAPANESE = ("祖父", "じいちゃん", "爺ちゃん", "じっちゃん")
MATERNAL_GRANDCHILDREN = ("Masaomi", "")
PATERNAL_GRANDCHILDREN = ("Rentarou", "Koharu")
SOMEONE_ELSES_GRANDFATHER = re.compile("(?<![俺私僕])の(?:お|御)?(?:祖父|じい|爺|じっ)")
PATERNAL_GRANDFATHER = "ปู่"
MATERNAL_GRANDFATHER = "ตา"
ADDRESSED_MATERNAL_GRANDFATHER = "คุณตา"
NOT_KINSHIP_PREFIXES = ("สาย", "ดวง", "น้ำ", "ลืม", "หลับ", "แวว", "นัยน์", "สบ", "พริบ",
                        "ขยิบ", "จับ", "ต่อ", "เ", "ส", "ลูก", "เบิก", "หรี่", "ปิด", "เปิด",
                        "ขยี้", "หู", "หน้า", "ถูก", "สะดุด", "ติด", "คา", "เต็ม", "กับ", "แก้ว",
                        "ขอบ", "เปลือก", "ขน", "มอง", "ละสาย", "ทาง", "ใน", "ตั้ง", "แก่", "ม่าน",
                        "ลับ", "ผิด", "คลาด", "ละลาน", "สุด", "ไม่วาง", "วาง", "ทันตั้ง", "นัย",
                        "หาง", "ชำเลือง", "เตะ", "ทอด", "กลอก", "ปรือ", "ตื่น", "ลาน", "เจ้า")
NOT_KINSHIP_SUFFIXES = ("ม", "ย", "ก", "ร", "ล", "ข่าย", "ชั่ง", "โต", "ค้าง", "แป๋ว", "ถลน",
                        "เขียว", "แดง", "พร่า", "ฝาด", "บอด", "คู่", "แก่", "ลุง", "เป็นประกาย",
                        "ตุ่ม", "ต่อตา", "เปล่า", "ทั้งสอง", "สองข้าง", "กลม", "เบิก", "ปริบ",
                        "ไม่กะพริบ", "ถึง", "สว่าง", "ทิพย์", "ที่สาม", "แหลม", "ไว", "ดี", "เล็ก",
                        "ขวา", "ซ้าย", "เดียว", "เยิ้ม", "ลอย", "ปรือ", "วาว", "ลุก", "เหลือก",
                        "ขาว", "ดำ", "หยี", "ตี่", "ชั้น", "ต่ำ", "ไม่ฝาด", "ตัวเอง", "เนื้อ")
MATERNAL_GRANDFATHER_PATTERN = re.compile(
    "".join("(?<!%s)" % prefix for prefix in NOT_KINSHIP_PREFIXES)
    + MATERNAL_GRANDFATHER + "(?!%s)" % "|".join(NOT_KINSHIP_SUFFIXES))

RUBY = re.compile(r"\[[^\]]*\]")
FORMAT_TAG = re.compile(r"%\d+;")
LEADING_FORMAT_TAGS = re.compile(r"^(?:%\d+;)+")
LITERAL_LINE_BREAK = "\\n"

THAI_BLOCK_START, THAI_BLOCK_END = 0x0E00, 0x0E7F
PRINTABLE_ASCII_START, PRINTABLE_ASCII_END = 0x20, 0x7E
GAME_FONT_SYMBOLS = frozenset("「」『』【】（）、。・〜～…―—！？♪“”‘’")


def finding(record: Record, rule: str, severity: str, problem: str) -> Finding:
    return Finding(record.chapter, record.idx, rule, severity, problem, LINT)


def own_words(thai: str) -> str:
    text = thai.strip()
    if text[:1] in OUTER_BRACKETS and text.endswith(OUTER_BRACKETS[text[:1]]):
        text = text[1:-1]
    return INNER_QUOTATION.sub("", text)


def speaker_sex(record: Record, tables: Tables) -> list[Finding]:
    if not record.speaker:
        return []
    sex = tables.sex_of(record.speaker)
    spoken = own_words(record.th)
    if sex == FEMALE:
        markers = [MALE_PARTICLE] if MALE_PARTICLE in spoken else []
        if (MALE_PRONOUN_PATTERN.search(spoken)
                and not any(hair in record.jp for hair in HAIR_IN_JAPANESE)):
            markers.append(MALE_PRONOUN)
        return [finding(record, "C1", MAJOR, "female speaker uses male " + " ".join(markers))] \
            if markers else []
    if sex == MALE:
        markers = [marker for marker in FEMALE_MARKERS if marker in spoken]
        return [finding(record, "C1", MAJOR, "male speaker uses female " + " ".join(markers))] \
            if markers else []
    return []


def kinship_side(record: Record, tables: Tables) -> list[Finding]:
    if not any(word in record.jp for word in GRANDFATHER_IN_JAPANESE):
        return []
    if (record.speaker in MATERNAL_GRANDCHILDREN and PATERNAL_GRANDFATHER in record.th
            and not SOMEONE_ELSES_GRANDFATHER.search(record.jp)):
        return [finding(record, "C3", MAJOR,
                        "Genjuurou is Masaomi's maternal grandfather: ตา, not ปู่")]
    if record.speaker in PATERNAL_GRANDCHILDREN and (
            ADDRESSED_MATERNAL_GRANDFATHER in record.th
            or (PATERNAL_GRANDFATHER not in record.th
                and MATERNAL_GRANDFATHER_PATTERN.search(record.th))):
        return [finding(record, "C3", MAJOR,
                        "Genjuurou is %s's paternal grandfather: ปู่, not ตา" % record.speaker)]
    return []


def glossary_matches(japanese: str, glossary: tuple) -> list[GlossaryEntry]:
    candidates = sorted(((term, entry) for entry in glossary for term in entry.jp_terms),
                        key=lambda candidate: -len(candidate[0]))
    covered: set[int] = set()
    matched: list[GlossaryEntry] = []
    for term, entry in candidates:
        starts = [match.start() for match in re.finditer(re.escape(term), japanese)]
        free = [start for start in starts if start not in covered]
        for start in starts:
            covered.update(range(start, start + len(term)))
        if free and entry not in matched:
            matched.append(entry)
    return matched


def thai_without_longer_terms(thai: str, entry: GlossaryEntry, matched: list) -> str:
    for other in matched:
        if other is not entry and entry.th in other.th:
            thai = thai.replace(other.th, "")
    return thai


def glossary_term_missing(record: Record, tables: Tables) -> list[Finding]:
    matched = glossary_matches(record.jp, tables.glossary)
    return [finding(record, "N1", MINOR, "glossary term %s is not rendered as %s"
                    % (entry.en, entry.th))
            for entry in matched
            if entry.th not in thai_without_longer_terms(record.th, entry, matched)]


def glossary_forbidden_rendering(record: Record, tables: Tables) -> list[Finding]:
    return [finding(record, "N2", MAJOR, "forbidden rendering %s for %s, use %s"
                    % (wrong, entry.en, entry.th))
            for entry in glossary_matches(record.jp, tables.glossary)
            for wrong in entry.forbidden
            if wrong in record.th.replace(entry.th, "")]


def quote_brackets(record: Record, tables: Tables) -> list[Finding]:
    japanese = mt.opener(record.jp), mt.closer(record.jp)
    thai = mt.opener(record.th), mt.closer(record.th)
    if not record.th.strip() or japanese == thai:
        return []
    return [finding(record, "F1", MAJOR, "quote brackets %s%s in Japanese but %s%s in Thai"
                    % (japanese + thai))]


def japanese_left_in_thai(record: Record, tables: Tables) -> list[Finding]:
    return [finding(record, "F2", MAJOR, "kana or kanji left in the Thai")] \
        if mt.KANA_HAN.search(record.th) else []


def thai_empty(record: Record, tables: Tables) -> list[Finding]:
    return [finding(record, "F3", MAJOR, "Thai is empty")] \
        if not record.th.strip() and mt.WORDS.search(record.jp) else []


def outside_game_font(thai: str) -> list[str]:
    return sorted({character for character in thai
                   if not (THAI_BLOCK_START <= ord(character) <= THAI_BLOCK_END
                           or PRINTABLE_ASCII_START <= ord(character) <= PRINTABLE_ASCII_END
                           or character in GAME_FONT_SYMBOLS
                           or mt.KANA_HAN.match(character))})


def undrawable_characters(record: Record, tables: Tables) -> list[Finding]:
    undrawable = outside_game_font(record.th)
    return [finding(record, "F5", MAJOR, "characters the game font cannot draw: %s"
                    % " ".join("U+%04X" % ord(character) for character in undrawable))] \
        if undrawable else []


def format_tags(record: Record, tables: Tables) -> list[Finding]:
    if not record.th.strip():
        return []
    japanese_tags = len(FORMAT_TAG.findall(record.jp))
    leading = LEADING_FORMAT_TAGS.match(record.jp.strip())
    droppable = len(FORMAT_TAG.findall(leading.group(0))) if leading else 0
    thai_tags = len(FORMAT_TAG.findall(record.th))
    problems = []
    if thai_tags not in (japanese_tags, japanese_tags - droppable):
        problems.append("%d format tags in Japanese, %d in Thai" % (japanese_tags, thai_tags))
    if record.jp.count(LITERAL_LINE_BREAK) != record.th.count(LITERAL_LINE_BREAK):
        problems.append("literal line break count differs")
    return [finding(record, "F4", MINOR, "; ".join(problems))] if problems else []


def bare_text(text: str) -> str:
    return FORMAT_TAG.sub("", RUBY.sub("", text)).strip()


def thai_to_japanese_ratio(record: Record) -> float | None:
    japanese = bare_text(record.jp)
    if len(japanese) < SUMMARIZATION_MINIMUM_JAPANESE or not record.th.strip():
        return None
    return len(bare_text(record.th)) / len(japanese)


def possible_summarization(record: Record, tables: Tables) -> list[Finding]:
    ratio = thai_to_japanese_ratio(record)
    if ratio is None or ratio >= tables.summarization_ratio:
        return []
    return [finding(record, "S2", MINOR, "possible summarization: Thai is %.2f of the "
                    "Japanese length" % ratio)]


RULES = {
    "C1": speaker_sex,
    "C3": kinship_side,
    "N1": glossary_term_missing,
    "N2": glossary_forbidden_rendering,
    "F1": quote_brackets,
    "F2": japanese_left_in_thai,
    "F3": thai_empty,
    "F4": format_tags,
    "F5": undrawable_characters,
    "S2": possible_summarization,
}


def lint_record(record: Record, tables: Tables, rule_ids=tuple(RULES)) -> list[Finding]:
    return [found for rule_id in rule_ids for found in RULES[rule_id](record, tables)]


def lint_records(records: list[Record], tables: Tables) -> list[Finding]:
    return [found for record in records for found in lint_record(record, tables)]


def count_by(findings: list[Finding], field: str) -> list[tuple[str, int]]:
    counts = collections.Counter(getattr(found, field) for found in findings)
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))


def selected_records(workspace: Workspace, chapters: list[str]) -> list[Record]:
    return [record for record in workspace_module.load_records(workspace)
            if not chapters or record.chapter in chapters]


def run(workspace: Workspace, chapters: list[str]) -> int:
    records = selected_records(workspace, chapters)
    findings = lint_records(records, load_tables(workspace, SUMMARIZATION_RATIO))
    workspace_module.write_shapes(workspace.lint_file, findings)
    print("%d Records, %d Findings, S2 ratio %.2f" % (len(records), len(findings),
                                                      SUMMARIZATION_RATIO))
    for rule_id in RULES:
        print("  %s %d" % (rule_id, sum(1 for found in findings if found.rule == rule_id)))
    for chapter, count in count_by(findings, "chapter"):
        print("  chapter %s %d" % (chapter, count))
    print("wrote", workspace.lint_file)
    return 1 if findings else 0
