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
            space = synthetic.build_workspace(directory, [record("「ทดสอบ」")])
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


if __name__ == "__main__":
    unittest.main()
