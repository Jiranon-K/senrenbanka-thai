from __future__ import annotations

import ast
import contextlib
import csv
import io
import json
import os
import sys
import tempfile
import tokenize
import unittest

PACKAGE_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PACKAGE_DIRECTORY)

import evidence

SCENARIO_FILE = "sample.ks.json"

YOSHINO = evidence.VndbCharacter("c1", "Tomotake Yoshino", "朝武 芳乃", evidence.FEMALE, "", "primary")
YASUHARU = evidence.VndbCharacter("c2", "Tomotake Yasuharu", "朝武 安晴", evidence.MALE, "", "side")
LENA = evidence.VndbCharacter("c3", "Lena Liechtenauer", "レナ・リヒテナウアー", evidence.FEMALE, "", "primary")
MASAOMI = evidence.VndbCharacter("c4", "Arichi Masaomi", "有地 将臣", evidence.MALE, "", "main")
CAST = [YOSHINO, YASUHARU, LENA, MASAOMI]


def line(speaker_en, japanese_text, japanese_label, voice_owner=None, chinese_label=""):
    return evidence.SpokenLine(speaker_en, japanese_text, japanese_label,
                               voice_owner or japanese_label, chinese_label)


def speaker(speaker_en, japanese_label, voice_owner="", pronouns=evidence.PronounCounts(), lines=1):
    return evidence.SpeakerEvidence(speaker_en, lines, japanese_label, "", voice_owner, pronouns)


def scenario_entry(voice_owner, shown_override, english_label, chinese_label, japanese_text):
    return [voice_owner, shown_override,
            [[shown_override, japanese_text], [english_label, "english"],
             [english_label, "thai"], [chinese_label, "chinese"]],
            None, 0, {}]


def vndb_payload(records):
    return {"vn_id": "v1", "vn_search": {"results": []},
            "character_pages": [{"more": False, "results": records}]}


def vndb_record(identifier, name, original, sex_code):
    return {"id": identifier, "name": name, "original": original, "age": None,
            "sex": [sex_code, sex_code], "vns": [{"id": "v1", "role": "side"}]}


class Workspace:
    def __init__(self, directory, entries, records):
        self.strings = os.path.join(directory, "strings.csv")
        self.scenarios = directory
        self.cache = os.path.join(directory, "cache", "vndb.json")
        self.output = os.path.join(directory, "characters.csv")
        self.write_scenario(entries)
        self.write_strings(entries)
        self.write_cache(records)

    def write_scenario(self, entries):
        with open(os.path.join(self.scenarios, SCENARIO_FILE), "w", encoding="utf-8") as scenario_file:
            json.dump({"scenes": [{"texts": entries, "data": CONTROL_BLOCK}]}, scenario_file, ensure_ascii=False)

    def write_strings(self, entries):
        with open(self.strings, "w", encoding="utf-8-sig", newline="") as strings_file:
            writer = csv.writer(strings_file)
            writer.writerow(["file", "idx", "speaker_en", "jp", "en", "th"])
            for index, entry in enumerate(entries):
                writer.writerow([SCENARIO_FILE, index, entry[2][1][0] or "", entry[2][0][1], "english", ""])
            writer.writerow([SCENARIO_FILE, len(entries), "face", "stage", "stage", ""])
            writer.writerow([SCENARIO_FILE, "ch0", "(choice)", "選択", "choice", ""])

    def write_cache(self, records):
        os.makedirs(os.path.dirname(self.cache))
        with open(self.cache, "w", encoding="utf-8") as cache_file:
            json.dump(vndb_payload(records), cache_file, ensure_ascii=False)

    def run(self):
        with contextlib.redirect_stdout(io.StringIO()) as captured:
            exit_code = evidence.main(["--strings", self.strings, "--scenarios", self.scenarios,
                                       "--cache", self.cache, "--output", self.output])
        return exit_code, captured.getvalue()

    def rows(self):
        with open(self.output, encoding="utf-8-sig", newline="") as characters_file:
            return list(csv.DictReader(characters_file))

    def rewrite_rows(self, rows):
        with open(self.output, "w", encoding="utf-8-sig", newline="") as characters_file:
            writer = csv.DictWriter(characters_file, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)


AGREEING_ENTRIES = (
    [scenario_entry("芳乃", None, "Yoshino", "芳乃", "私は行きます") for _ in range(3)]
    + [scenario_entry("将臣", None, "Masaomi", "將臣", "俺が行く") for _ in range(6)]
    + [scenario_entry("旅人", None, "Traveller", "旅人", "こんにちは")]
)
CONTROL_BLOCK = [["bgm", "stage"], ["face", "stage"], ["bgm", "stage"], ["bgm", "stage"]]
AGREEING_RECORDS = [vndb_record("c1", "Tomotake Yoshino", "朝武 芳乃", "f"),
                    vndb_record("c4", "Arichi Masaomi", "有地 将臣", "m")]


class PronounThresholds(unittest.TestCase):
    def test_heroine_quoting_male_pronouns_among_thousands_of_neutral_lines_stays_unsexed(self):
        lines = ([line("Heroine", "私はここにいます", "芳乃") for _ in range(3000)]
                 + [line("Heroine", "「俺に任せろ」と言われました", "芳乃") for _ in range(8)])
        heroine = evidence.summarise_speakers(lines)[0]
        self.assertEqual(heroine.pronouns.male, 8)
        self.assertEqual(evidence.pronoun_sex(heroine.pronouns), "")
        self.assertEqual(evidence.character_row(heroine, CAST, evidence.HandMaintained()).sex,
                         evidence.FEMALE)

    def test_habitual_male_pronoun_is_male(self):
        self.assertEqual(evidence.pronoun_sex(evidence.PronounCounts(male=40, neutral=3)), evidence.MALE)

    def test_habitual_female_pronoun_is_female(self):
        self.assertEqual(evidence.pronoun_sex(evidence.PronounCounts(female=9, neutral=1)), evidence.FEMALE)

    def test_four_gendered_hits_are_not_enough(self):
        self.assertEqual(evidence.pronoun_sex(evidence.PronounCounts(male=4)), "")

    def test_five_gendered_hits_are_enough(self):
        self.assertEqual(evidence.pronoun_sex(evidence.PronounCounts(male=5)), evidence.MALE)

    def test_gendered_share_below_thirty_percent_is_no_signal(self):
        self.assertEqual(evidence.pronoun_sex(evidence.PronounCounts(male=29, neutral=71)), "")

    def test_gendered_share_of_thirty_percent_is_a_signal(self):
        self.assertEqual(evidence.pronoun_sex(evidence.PronounCounts(male=30, neutral=70)), evidence.MALE)

    def test_agreement_below_eighty_percent_is_no_signal(self):
        self.assertEqual(evidence.pronoun_sex(evidence.PronounCounts(male=7, female=3)), "")

    def test_agreement_of_eighty_percent_is_a_signal(self):
        self.assertEqual(evidence.pronoun_sex(evidence.PronounCounts(male=8, female=2)), evidence.MALE)

    def test_no_pronouns_is_no_signal(self):
        self.assertEqual(evidence.pronoun_sex(evidence.PronounCounts()), "")


class PronounCounting(unittest.TestCase):
    def test_each_pronoun_lands_in_its_group(self):
        self.assertEqual(evidence.count_pronouns("俺とオレと僕とボク"), evidence.PronounCounts(male=4))
        self.assertEqual(evidence.count_pronouns("あたしとアタシとわたくし"), evidence.PronounCounts(female=3))
        self.assertEqual(evidence.count_pronouns("わたしと私と自分と吾輩"), evidence.PronounCounts(neutral=4))

    def test_katakana_words_containing_a_pronoun_are_not_pronouns(self):
        self.assertEqual(evidence.count_pronouns("オレンジとカフェオレとボクシング"), evidence.PronounCounts())

    def test_shared_speaker_lines_are_skipped(self):
        lines = ([line("Pair", "俺たちは行く", "芳乃/将臣") for _ in range(10)]
                 + [line("Pair", "俺たちは行く", "芳乃＆将臣") for _ in range(10)])
        self.assertEqual(evidence.summarise_speakers(lines)[0].pronouns, evidence.PronounCounts())


class LabelWords(unittest.TestCase):
    def test_gender_words_in_the_japanese_label(self):
        self.assertEqual(evidence.label_word_sex("外国人女性Ａ"), evidence.FEMALE)
        self.assertEqual(evidence.label_word_sex("茉子の母"), evidence.FEMALE)
        self.assertEqual(evidence.label_word_sex("芦花の父親"), evidence.MALE)
        self.assertEqual(evidence.label_word_sex("おじさん"), evidence.MALE)

    def test_label_without_gender_word_is_no_signal(self):
        self.assertEqual(evidence.label_word_sex("運転手"), "")

    def test_label_with_both_kinds_of_word_is_no_signal(self):
        self.assertEqual(evidence.label_word_sex("祖父・パパ・ママ"), "")


class VndbMatching(unittest.TestCase):
    def test_given_name_matches(self):
        self.assertIs(evidence.character_named("芳乃", CAST), YOSHINO)

    def test_full_name_matches(self):
        self.assertIs(evidence.character_named("朝武芳乃", CAST), YOSHINO)

    def test_given_name_written_first_matches(self):
        self.assertIs(evidence.character_named("レナ", CAST), LENA)

    def test_family_name_shared_by_two_characters_matches_nobody(self):
        self.assertIsNone(evidence.character_named("朝武", CAST))

    def test_romanised_name_matches_nobody(self):
        self.assertIsNone(evidence.character_named("Yoshino", CAST))

    def test_question_mark_and_voice_suffix_still_match(self):
        self.assertEqual(evidence.characters_behind(speaker("Yoshino?", "芳乃？"), CAST), [YOSHINO])
        self.assertEqual(evidence.characters_behind(speaker("Lena's Voice", "レナの声"), CAST), [LENA])

    def test_generic_label_falls_back_to_its_single_voice_owner(self):
        self.assertEqual(evidence.characters_behind(speaker("Girl", "女の子", "レナ"), CAST), [LENA])

    def test_generic_label_with_several_voice_owners_matches_nobody(self):
        lines = [line("Voice", "あ", "声", "レナ"), line("Voice", "あ", "声", "芳乃")]
        self.assertEqual(evidence.characters_behind(evidence.summarise_speakers(lines)[0], CAST), [])

    def test_shared_label_with_an_unmatched_member_matches_nobody(self):
        self.assertEqual(evidence.characters_behind(speaker("Lena, Stranger", "レナ・旅人", "レナ"), CAST), [])

    def test_parse_keeps_structured_fields_and_first_sex_entry(self):
        record = {"id": "c9", "name": "Name", "original": "名 前", "age": 500,
                  "sex": ["f", "m"], "description": "free text",
                  "vns": [{"id": "v2", "role": "appears"}, {"id": "v1", "role": "primary"}]}
        self.assertEqual(evidence.parse_vndb_characters(vndb_payload([record])),
                         [evidence.VndbCharacter("c9", "Name", "名 前", evidence.FEMALE, "500", "primary")])

    def test_original_release_is_the_2016_one(self):
        search_response = {"results": [{"id": "v9", "released": "2019-01-01"},
                                       {"id": "v1", "released": "2016-07-29"}]}
        self.assertEqual(evidence.original_release_id(search_response), "v1")


class EvidenceLevels(unittest.TestCase):
    def row(self, described):
        return evidence.character_row(described, CAST, evidence.HandMaintained())

    def test_vndb_and_ingame_agreeing_is_locked(self):
        row = self.row(speaker("Masaomi", "将臣", pronouns=evidence.PronounCounts(male=50)))
        self.assertEqual((row.sex_vndb, row.sex_ingame, row.sex, row.evidence),
                         (evidence.MALE, evidence.MALE, evidence.MALE, evidence.LOCKED))

    def test_vndb_without_ingame_contradiction_is_locked(self):
        row = self.row(speaker("Yoshino", "芳乃"))
        self.assertEqual((row.sex_ingame, row.sex, row.evidence), ("", evidence.FEMALE, evidence.LOCKED))

    def test_ingame_only_is_provisional(self):
        row = self.row(speaker("Foreign Woman A", "外国人女性Ａ"))
        self.assertEqual((row.sex_vndb, row.sex, row.evidence), ("", evidence.FEMALE, evidence.PROVISIONAL))

    def test_no_source_is_unknown(self):
        row = self.row(speaker("Taxi Driver", "運転手"))
        self.assertEqual((row.sex, row.evidence), ("", evidence.UNKNOWN))

    def test_vndb_against_pronouns_is_conflict(self):
        row = self.row(speaker("Yoshino", "芳乃", pronouns=evidence.PronounCounts(male=50)))
        self.assertEqual((row.sex, row.evidence), ("", evidence.CONFLICT))

    def test_label_word_against_pronouns_is_conflict(self):
        row = self.row(speaker("Woman", "女性", pronouns=evidence.PronounCounts(male=50)))
        self.assertEqual((row.sex_ingame, row.evidence), (evidence.DISPUTED, evidence.CONFLICT))

    def test_shared_label_of_both_sexes_is_mixed_not_conflict(self):
        row = self.row(speaker("Yoshino, Masaomi", "芳乃・将臣"))
        self.assertEqual((row.sex, row.evidence, row.vndb_name),
                         (evidence.MIXED, evidence.LOCKED, "Tomotake Yoshino + Arichi Masaomi"))


class EndToEnd(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

    def workspace(self, entries, records):
        return Workspace(self.directory.name, entries, records)

    def test_agreeing_sources_exit_zero_sorted_by_lines(self):
        workspace = self.workspace(AGREEING_ENTRIES, AGREEING_RECORDS)
        exit_code, _ = workspace.run()
        rows = workspace.rows()
        self.assertEqual(exit_code, 0)
        self.assertEqual(list(rows[0]), list(evidence.COLUMNS))
        self.assertEqual([(row["speaker_en"], row["lines"], row["sex"], row["evidence"]) for row in rows],
                         [("Masaomi", "6", "male", "locked"), ("Yoshino", "3", "female", "locked"),
                          ("Traveller", "1", "", "unknown")])
        self.assertEqual((rows[0]["jp_label"], rows[0]["cn_label"]), ("将臣", "將臣"))

    def test_conflict_exits_non_zero_and_is_printed(self):
        entries = [scenario_entry("芳乃", None, "Yoshino", "芳乃", "俺が行く") for _ in range(6)]
        workspace = self.workspace(entries, AGREEING_RECORDS)
        exit_code, printed = workspace.run()
        self.assertNotEqual(exit_code, 0)
        self.assertIn("CONFLICT Yoshino", printed)
        self.assertEqual(workspace.rows()[0]["evidence"], "CONFLICT")

    def test_regeneration_preserves_hand_maintained_columns(self):
        workspace = self.workspace(AGREEING_ENTRIES, AGREEING_RECORDS)
        workspace.run()
        edited = workspace.rows()
        edited[1].update(thai_self_pronoun="ฉัน", thai_polite_particle="ค่ะ", notes="formal", sex="male")
        workspace.rewrite_rows(edited)
        workspace.run()
        yoshino = workspace.rows()[1]
        self.assertEqual((yoshino["thai_self_pronoun"], yoshino["thai_polite_particle"], yoshino["notes"]),
                         ("ฉัน", "ค่ะ", "formal"))
        self.assertEqual(yoshino["sex"], "female")
        self.assertEqual(workspace.rows()[0]["notes"], "")

    def test_strings_and_scenario_out_of_step_stop_the_run(self):
        workspace = self.workspace(AGREEING_ENTRIES, AGREEING_RECORDS)
        workspace.write_scenario(list(reversed(AGREEING_ENTRIES)))
        with self.assertRaises(SystemExit):
            workspace.run()


class VndbCache(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.cache = os.path.join(directory.name, "mt", "vndb.json")
        self.fetches = []

    def fetch(self):
        self.fetches.append(1)
        return vndb_payload([vndb_record("c1", "Name", "名 前", "f")])

    def test_second_load_reads_the_cache_without_fetching(self):
        first = evidence.load_vndb_payload(self.cache, False, self.fetch)
        second = evidence.load_vndb_payload(self.cache, False, self.fetch)
        self.assertEqual((first, len(self.fetches)), (second, 1))

    def test_refresh_fetches_again(self):
        evidence.load_vndb_payload(self.cache, False, self.fetch)
        evidence.load_vndb_payload(self.cache, True, self.fetch)
        self.assertEqual(len(self.fetches), 2)


class NoComments(unittest.TestCase):
    def sources(self):
        return [os.path.join(PACKAGE_DIRECTORY, name)
                for name in sorted(os.listdir(PACKAGE_DIRECTORY)) if name.endswith(".py")]

    def test_no_comment_tokens(self):
        for source in self.sources():
            with open(source, "rb") as source_file:
                comments = [token for token in tokenize.tokenize(source_file.readline)
                            if token.type == tokenize.COMMENT]
            self.assertEqual(comments, [], source)

    def test_no_docstrings(self):
        for source in self.sources():
            with open(source, encoding="utf-8") as source_file:
                tree = ast.parse(source_file.read())
            documented = [node for node in ast.walk(tree)
                          if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef))
                          and ast.get_docstring(node) is not None]
            self.assertEqual(documented, [], source)


if __name__ == "__main__":
    unittest.main()
