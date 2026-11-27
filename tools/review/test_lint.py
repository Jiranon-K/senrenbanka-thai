from __future__ import annotations

import tempfile
import unittest

from tools.review import lint, synthetic, workspace
from tools.review.synthetic import TABLES, record


def rules_hit(source, rule_id):
    return [found.rule for found in lint.RULES[rule_id](source, TABLES)]


class SpeakerSex(unittest.TestCase):
    def test_female_speaker_with_male_particle(self):
        self.assertEqual(rules_hit(record("「ขอบคุณครับ」"), "C1"), ["C1"])

    def test_female_speaker_with_male_pronoun(self):
        self.assertEqual(rules_hit(record("「ผมจะช่วยเองค่ะ」"), "C1"), ["C1"])

    def test_male_speaker_with_female_markers(self):
        for thai in ("「ขอบคุณค่ะ」", "「ดีจังนะคะ」", "「ดิฉันเอง」"):
            self.assertEqual(rules_hit(record(thai, speaker="Masaomi"), "C1"), ["C1"], thai)

    def test_matching_particles_pass(self):
        self.assertEqual(rules_hit(record("「ขอบคุณค่ะ」"), "C1"), [])
        self.assertEqual(rules_hit(record("「ผมขอบคุณครับ」", speaker="Masaomi"), "C1"), [])

    def test_hair_compounds_are_not_the_pronoun(self):
        for thai in ("「ทรงผมใหม่สวยค่ะ」", "「ผมยาวจังค่ะ」", "「เส้นผมติดเสื้อค่ะ」",
                     "「ไปสระผมก่อนนะคะ」", "「ผมสีดำสวยค่ะ」"):
            self.assertEqual(rules_hit(record(thai), "C1"), [], thai)

    def test_hair_in_japanese_silences_the_pronoun(self):
        self.assertEqual(rules_hit(record("「ผมเปียกหมดแล้วค่ะ」", jp="「髪が濡れました」"), "C1"), [])

    def test_quoted_speech_is_ignored(self):
        self.assertEqual(rules_hit(record("「เขาบอกว่า『ขอบคุณครับ』ค่ะ」"), "C1"), [])
        self.assertEqual(rules_hit(record("「เธอพูดว่า “ไม่ค่ะ” นะ」", speaker="Masaomi"), "C1"), [])

    def test_whole_line_in_double_brackets_is_still_checked(self):
        self.assertEqual(rules_hit(record("『ขอบคุณครับ』", jp="『ありがとう』"), "C1"), ["C1"])

    def test_unknown_sex_and_narration_are_skipped(self):
        self.assertEqual(rules_hit(record("「ขอบคุณครับค่ะ」", speaker="Beast"), "C1"), [])
        self.assertEqual(rules_hit(record("ดีจังเลยค่ะ", jp="これは試験です", speaker=""), "C1"), [])


class KinshipSide(unittest.TestCase):
    GRANDFATHER = "「祖父ちゃんに会った」"

    def test_masaomi_and_narration_must_not_say_paternal(self):
        self.assertEqual(rules_hit(record("「ไปหาคุณปู่มา」", self.GRANDFATHER, "Masaomi"), "C3"),
                         ["C3"])
        self.assertEqual(rules_hit(record("ผมไปหาปู่มา", "じいちゃんに会った", ""), "C3"), ["C3"])

    def test_masaomi_saying_maternal_passes(self):
        self.assertEqual(rules_hit(record("「ไปหาคุณตามา」", self.GRANDFATHER, "Masaomi"), "C3"), [])

    def test_someone_elses_grandfather_is_not_judged(self):
        self.assertEqual(rules_hit(record("「ปู่ของเธอใจดีนะ」", "「君のお祖父ちゃんは優しい」",
                                          "Masaomi"), "C3"), [])

    def test_cousins_must_not_say_maternal(self):
        for thai in ("「คุณตาโกรธแล้ว」", "「โดนตาดุอีกแล้ว」", "「ตา!」"):
            for speaker in ("Rentarou", "Koharu"):
                self.assertEqual(rules_hit(record(thai, self.GRANDFATHER, speaker), "C3"),
                                 ["C3"], thai)

    def test_other_words_containing_the_syllable_pass(self):
        for thai in ("「เดินตามปู่ไป」", "「สายตาน่ากลัว」", "「ดวงตาเป็นประกาย」", "「เกือบตายแล้ว」",
                     "「ดูตารางก่อน」", "「ตากผ้าอยู่」", "「ตามมาเร็ว」"):
            self.assertEqual(rules_hit(record(thai, self.GRANDFATHER, "Rentarou"), "C3"), [], thai)

    def test_no_grandfather_in_japanese_passes(self):
        self.assertEqual(rules_hit(record("「คุณตามาแล้ว」", speaker="Koharu"), "C3"), [])


class GlossaryTerms(unittest.TestCase):
    def test_missing_term(self):
        self.assertEqual(rules_hit(record("「เธอเป็นนักบวชหญิง」", "「巫女です」"), "N1"), ["N1"])

    def test_present_term(self):
        self.assertEqual(rules_hit(record("「เธอเป็นมิโกะ」", "「巫女です」"), "N1"), [])

    def test_longest_term_wins(self):
        findings = lint.glossary_term_missing(
            record("「ท่านคือมิโกะ」", "「巫女姫です」"), TABLES)
        self.assertEqual([found.problem.split()[2:4] for found in findings],
                         [["Shrine", "Princess"]])
        self.assertEqual(rules_hit(record("「ท่านคือองค์หญิงมิโกะ」", "「巫女姫です」"), "N1"), [])

    def test_short_term_still_judged_beside_the_long_one(self):
        self.assertEqual(rules_hit(record("「องค์หญิงมิโกะกับสาวศาลเจ้า」", "「巫女姫と巫女です」"), "N1"),
                         ["N1"])

    def test_alternative_japanese_terms(self):
        self.assertEqual(rules_hit(record("「เขาเป็นหมอผี」", "「祓い屋です」"), "N1"), ["N1"])

    def test_single_character_terms_are_skipped(self):
        self.assertEqual(rules_hit(record("「มีปีศาจ」", "「妖がいる」"), "N1"), [])

    def test_forbidden_rendering(self):
        self.assertEqual(rules_hit(record("「เรนทาโร่มาแล้ว」", "「廉太郎が来た」"), "N2"), ["N2"])

    def test_forbidden_prefix_of_the_correct_term_passes(self):
        self.assertEqual(rules_hit(record("「เร็นทาโร่มาแล้ว」", "「廉太郎が来た」"), "N2"), [])

    def test_forbidden_prefix_without_the_tone_mark_fires(self):
        self.assertEqual(rules_hit(record("「เร็นทาโรมาแล้ว」", "「廉太郎が来た」"), "N2"), ["N2"])

    def test_forbidden_needs_the_japanese_term(self):
        self.assertEqual(rules_hit(record("「เรนทาโร่มาแล้ว」"), "N2"), [])


class Form(unittest.TestCase):
    def test_brackets_must_match(self):
        self.assertEqual(rules_hit(record("ทดสอบ"), "F1"), ["F1"])
        self.assertEqual(rules_hit(record("『ทดสอบ』"), "F1"), ["F1"])
        self.assertEqual(rules_hit(record("「ทดสอบ」", jp="これは試験です"), "F1"), ["F1"])
        self.assertEqual(rules_hit(record("「ทดสอบ」"), "F1"), [])
        self.assertEqual(rules_hit(record("「ทดสอบ」", jp="%84;「これは試験です」"), "F1"), [])

    def test_japanese_left_in_thai(self):
        self.assertEqual(rules_hit(record("「ทดสอบです」"), "F2"), ["F2"])
        self.assertEqual(rules_hit(record("「ทดสอบ……！？」"), "F2"), [])

    def test_characters_outside_the_game_font(self):
        self.assertEqual(rules_hit(record("「ทดสอบ☆」"), "F5"), ["F5"])
        self.assertEqual(rules_hit(record("「ทด○○สอบ」"), "F5"), ["F5"])
        self.assertEqual(rules_hit(record("「ทดสอบ♪……！？ ABC 12*」"), "F5"), [])

    def test_empty_thai(self):
        self.assertEqual(rules_hit(record(" "), "F3"), ["F3"])
        self.assertEqual(rules_hit(record("", jp="……"), "F3"), [])
        self.assertEqual(rules_hit(record("「ทดสอบ」"), "F3"), [])

    def test_format_tags(self):
        self.assertEqual(rules_hit(record("「ทดสอบ」", jp="「これは%84;試験です」"), "F4"), ["F4"])
        self.assertEqual(rules_hit(record("「ทด%84;สอบ」", jp="「これは%84;試験です」"), "F4"), [])
        self.assertEqual(rules_hit(record("「ทดสอบ」", jp="%84;「これは試験です」"), "F4"), [])
        self.assertEqual(rules_hit(record("%84;「ทดสอบ」", jp="%84;「これは試験です」"), "F4"), [])

    def test_literal_line_breaks(self):
        self.assertEqual(rules_hit(record("「ทดสอบ」", jp="「これは\\n試験です」"), "F4"), ["F4"])
        self.assertEqual(rules_hit(record("「ทด\\nสอบ」", jp="「これは\\n試験です」"), "F4"), [])


class Summarization(unittest.TestCase):
    LONG = "「" + "これは長い試験の文です" * 3 + "」"

    def test_short_thai_for_long_japanese(self):
        self.assertEqual(rules_hit(record("「ทดสอบ」", jp=self.LONG), "S2"), ["S2"])

    def test_full_length_thai_passes(self):
        self.assertEqual(rules_hit(record("「" + "นี่คือประโยคทดสอบที่ยาว" * 3 + "」", jp=self.LONG),
                                   "S2"), [])

    def test_short_japanese_is_not_judged(self):
        self.assertEqual(rules_hit(record("「อืม」"), "S2"), [])

    def test_ruby_and_tags_do_not_count_as_japanese_length(self):
        padded = "「" + "[よみ]" * 10 + "%84;これは試験です」"
        self.assertEqual(rules_hit(record("「ทดสอบ」", jp=padded), "S2"), [])


class Command(unittest.TestCase):
    def test_writes_findings_and_exits_one(self):
        with tempfile.TemporaryDirectory() as directory:
            space = synthetic.build_workspace(directory, [
                record("「ขอบคุณครับ」", idx="1"), record("「ขอบคุณค่ะ」", idx="2")],
                with_rules=False)
            self.assertEqual(lint.run(space, []), 1)
            saved = workspace.read_findings(space.lint_file)
            self.assertEqual([(found.idx, found.rule, found.source) for found in saved],
                             [("1", "C1", "lint")])

    def test_clean_data_exits_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            space = synthetic.build_workspace(directory, [record("「ขอบคุณค่ะ」")],
                                              with_rules=False)
            self.assertEqual(lint.run(space, []), 0)

    def test_every_rule_is_registered(self):
        self.assertEqual(sorted(lint.RULES),
                         ["C1", "C3", "F1", "F2", "F3", "F4", "F5", "N1", "N2", "S2"])


if __name__ == "__main__":
    unittest.main()
