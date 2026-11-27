from __future__ import annotations

import contextlib
import io
import os
import tempfile
import unittest

from tools.review import apply, revert, synthetic, workspace
from tools.review.shapes import Arbitration, Revision
from tools.review.synthetic import CHAPTER, record
from tools.review.test_apply import read_bytes, strings_thai

ORIGINAL_TEXT = "「ข้อความเดิม」"
CURRENT_TEXT = "「ข้อความใหม่」"
RECORDS = [record("「บรรทัดหนึ่ง」", idx="1"), record(CURRENT_TEXT, idx="2"),
           record("「บรรทัดสาม」", idx="3"), record("「แก้ด้วยมือ」", idx="4"),
           record(CURRENT_TEXT, idx="5")]
ARBITRATIONS = [
    Arbitration(CHAPTER, "2", ORIGINAL_TEXT, CURRENT_TEXT, "original", "meaning"),
    Arbitration(CHAPTER, "3", "「เดิมสาม」", "「บรรทัดสาม」", "current", "meaning"),
    Arbitration(CHAPTER, "4", ORIGINAL_TEXT, CURRENT_TEXT, "original", "meaning"),
    Arbitration(CHAPTER, "5", ORIGINAL_TEXT, CURRENT_TEXT, "same", "equal")]


def run_quietly(space):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        revert.run(space, [], True)
    return output.getvalue()


class Revert(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.space = synthetic.build_workspace(self.directory.name, RECORDS)
        workspace.write_shapes(self.space.arbitration_file(CHAPTER), ARBITRATIONS)

    def test_restores_only_the_line_the_arbiter_gave_to_the_original(self):
        before = read_bytes(self.space.thai_file(CHAPTER))
        printed = run_quietly(self.space)
        expected = before.replace(("2\t" + CURRENT_TEXT).encode(),
                                  ("2\t" + ORIGINAL_TEXT).encode(), 1)
        self.assertEqual(read_bytes(self.space.thai_file(CHAPTER)), expected)
        self.assertEqual(expected.count(b"\r\n"), 5)
        self.assertIn("reverted 1, already reverted 0, stale 1", printed)
        self.assertEqual(strings_thai(self.space)["2"], ORIGINAL_TEXT)
        self.assertEqual(strings_thai(self.space)["5"], CURRENT_TEXT)

    def test_byte_order_mark_and_unix_newlines_survive(self):
        path = self.space.thai_file(CHAPTER)
        marked = apply.BYTE_ORDER_MARK + read_bytes(path).replace(b"\r\n", b"\n")
        with open(path, "wb") as thai_file:
            thai_file.write(marked)
        run_quietly(self.space)
        self.assertEqual(read_bytes(path), marked.replace(
            ("2\t" + CURRENT_TEXT).encode(), ("2\t" + ORIGINAL_TEXT).encode(), 1))

    def test_logs_the_reversal(self):
        run_quietly(self.space)
        self.assertEqual(workspace.read_json_lines(self.space.changes_file), [{
            "chapter": CHAPTER, "idx": "2", "before": CURRENT_TEXT, "after": ORIGINAL_TEXT,
            "rules": ["ARB"], "problem": "arbiter preferred the original",
            "speaker": "Yoshino", "jp": "「これは試験です」"}])

    def test_second_revert_changes_nothing(self):
        run_quietly(self.space)
        watched = [self.space.thai_file(CHAPTER), self.space.strings_csv,
                   self.space.changes_file]
        first = [(read_bytes(path), os.stat(path).st_mtime_ns) for path in watched]
        printed = run_quietly(self.space)
        self.assertEqual([(read_bytes(path), os.stat(path).st_mtime_ns) for path in watched],
                         first)
        self.assertIn("reverted 0, already reverted 1, stale 1", printed)

    def test_stale_line_is_left_alone(self):
        workspace.write_shapes(self.space.arbitration_file(CHAPTER), [ARBITRATIONS[2]])
        before = read_bytes(self.space.thai_file(CHAPTER))
        printed = run_quietly(self.space)
        self.assertEqual(read_bytes(self.space.thai_file(CHAPTER)), before)
        self.assertEqual(workspace.read_json_lines(self.space.changes_file), [])
        self.assertIn("reverted 0, already reverted 0, stale 1", printed)

    def test_apply_does_not_bring_the_rewrite_back(self):
        kept = Revision(CHAPTER, "1", "「อื่น」", "「บรรทัดหนึ่ง」", ("S1",), "applied")
        workspace.write_shapes(self.space.revised_file(CHAPTER), [
            kept, Revision(CHAPTER, "2", ORIGINAL_TEXT, CURRENT_TEXT, ("S1",), "wrong meaning")])
        run_quietly(self.space)
        self.assertEqual(workspace.read_revisions(self.space.revised_file(CHAPTER)), [kept])
        with contextlib.redirect_stdout(io.StringIO()):
            apply.run(self.space, [CHAPTER], False)
        self.assertEqual(strings_thai(self.space)["2"], ORIGINAL_TEXT)


if __name__ == "__main__":
    unittest.main()
