from __future__ import annotations

import contextlib
import io
import re
import tempfile
import unittest

from tools.review import report, synthetic, workspace
from tools.review.synthetic import record

HOSTILE = "<script>alert(\"x\")</script> & 'quoted'"


def change(chapter, idx, rules, text=HOSTILE):
    return report.Change(chapter, idx, text, rules, text, text, text, text)


class Report(unittest.TestCase):
    def test_all_text_is_escaped(self):
        page = report.render([change("900", "1", ("S1",))])
        body = page[page.index("<body>"):page.index("<script>")]
        self.assertNotIn("<script>alert", body)
        self.assertNotIn("\"x\"", body)
        self.assertEqual(body.count("&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt; &amp; "
                                    "&#x27;quoted&#x27;"), 5)

    def test_hostile_chapter_and_rule_cannot_break_attributes(self):
        page = report.render([change("9\"><b>", "1", ("S\"1<",))])
        self.assertNotIn("9\"><b>", page)
        self.assertNotIn("S\"1<", page)
        self.assertIn("data-chapter=\"9&quot;&gt;&lt;b&gt;\"", page)

    def test_counts_and_filters(self):
        page = report.render([change("900", "1", ("S1", "C1"), "a"),
                              change("900", "2", ("S1",), "b"),
                              change("901", "1", ("N2",), "c")])
        self.assertIn("<h1>3 changed lines</h1>", page)
        self.assertIn("<li>S1 <b>2</b></li>", page)
        self.assertIn("<li>900 <b>2</b></li>", page)
        self.assertIn("<option value=\"901\">901</option>", page)
        self.assertIn("<option value=\"N2\">N2</option>", page)
        self.assertEqual(page.count("<article class=\"change\""), 3)

    def test_theme_frame_rules(self):
        page = report.render([change("900", "1", ("S1",), "a")])
        for variable in ("--foreground", "--muted-foreground", "--accent", "--border", "--card"):
            self.assertIn("var(%s)" % variable, page)
        self.assertIsNone(re.search(r"font-family|max-width|margin:\s*0 auto|https?://", page))
        self.assertIsNone(re.search(r"background:(?!\s*var\(--card\))", page))
        self.assertIsNone(re.search(r"#[0-9a-fA-F]{3,6}\b|rgb\(", page))

    def test_command_reads_the_change_log(self):
        with tempfile.TemporaryDirectory() as directory:
            space = synthetic.build_workspace(directory, [record("「ใหม่」")])
            workspace.append_json_line(space.changes_file, {
                "chapter": "900", "idx": "1", "before": "「เก่า」", "after": "「ใหม่」",
                "rules": ["S1"], "problem": "wrong meaning", "speaker": "",
                "jp": "「これは試験です」"})
            with contextlib.redirect_stdout(io.StringIO()):
                report.run(space)
            with open(space.report_file, encoding="utf-8") as report_file:
                page = report_file.read()
            self.assertIn("「ใหม่」", page)
            self.assertIn("<span>narration</span>", page)


def log_change(space, idx, before, after, rule):
    workspace.append_json_line(space.changes_file, {
        "chapter": "900", "idx": idx, "before": before, "after": after, "rules": [rule],
        "problem": "problem " + rule, "speaker": "Yoshino", "jp": "「これは試験です」"})


class NetChanges(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.space = synthetic.build_workspace(self.directory.name, [
            record("「สาม」", idx="1"), record("「เดิม」", idx="2"), record("「ห้า」", idx="3")])
        log_change(self.space, "1", "「หนึ่ง」", "「สอง」", "S1")
        log_change(self.space, "2", "「เดิม」", "「ใหม่」", "S1")
        log_change(self.space, "1", "「สอง」", "「สาม」", "C1")
        log_change(self.space, "2", "「ใหม่」", "「เดิม」", "ARB")
        log_change(self.space, "3", "「สี่」", "「แย่」", "S1")
        log_change(self.space, "3", "「แย่」", "「สี่」", "ARB")
        log_change(self.space, "3", "「สี่」", "「ห้า」", "N2")

    def test_line_revised_twice_shows_once_with_both_rules(self):
        changes = report.load_changes(self.space)
        self.assertEqual([(change.idx, change.before, change.after, change.rules)
                          for change in changes if change.idx == "1"],
                         [("1", "「หนึ่ง」", "「สาม」", ("S1", "C1"))])

    def test_reverted_line_is_omitted(self):
        self.assertEqual([change.idx for change in report.load_changes(self.space)],
                         ["1", "3"])

    def test_rules_restart_after_a_return_to_the_original(self):
        change = report.load_changes(self.space)[1]
        self.assertEqual((change.before, change.after, change.rules, change.problem),
                         ("「สี่」", "「ห้า」", ("N2",), "problem N2"))

    def test_page_counts_net_lines(self):
        with contextlib.redirect_stdout(io.StringIO()):
            report.run(self.space)
        with open(self.space.report_file, encoding="utf-8") as report_file:
            page = report_file.read()
        self.assertIn("<h1>2 changed lines</h1>", page)
        self.assertEqual(page.count("<article class=\"change\""), 2)
        self.assertNotIn("ARB", page)


if __name__ == "__main__":
    unittest.main()
