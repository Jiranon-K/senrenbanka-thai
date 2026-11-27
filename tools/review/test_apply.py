from __future__ import annotations

import contextlib
import csv
import io
import os
import tempfile
import unittest

from tools.review import apply, synthetic, workspace
from tools.review.shapes import Finding, Revision
from tools.review.synthetic import CHAPTER, record

RECORDS = [record("「บรรทัดหนึ่ง」", idx="1"), record("「บรรทัดสอง」", idx="2"),
           record("「บรรทัดสาม」", idx="3")]
REVISION = Revision(CHAPTER, "2", "「บรรทัดสอง」", "「บรรทัดที่แก้แล้ว」", ("S1",), "wrong meaning")


def read_bytes(path):
    with open(path, "rb") as source:
        return source.read()


def strings_thai(space):
    with open(space.strings_csv, encoding="utf-8-sig", newline="") as strings_file:
        return {row["idx"]: row["th"] for row in csv.DictReader(strings_file)}


def run_quietly(space):
    with contextlib.redirect_stdout(io.StringIO()):
        return apply.run(space, [CHAPTER], False)


class Apply(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.space = synthetic.build_workspace(self.directory.name, RECORDS)
        workspace.write_shapes(self.space.revised_file(CHAPTER), [REVISION])

    def test_changes_only_the_revised_line(self):
        before = read_bytes(self.space.thai_file(CHAPTER))
        run_quietly(self.space)
        after = read_bytes(self.space.thai_file(CHAPTER))
        self.assertEqual(after, before.replace("「บรรทัดสอง」".encode(), "「บรรทัดที่แก้แล้ว」".encode()))
        self.assertEqual(after.count(b"\r\n"), 3)
        self.assertFalse(after.startswith(apply.BYTE_ORDER_MARK))

    def test_mirrors_into_strings_and_keeps_its_byte_order_mark(self):
        run_quietly(self.space)
        self.assertEqual(strings_thai(self.space)["2"], "「บรรทัดที่แก้แล้ว」")
        self.assertEqual(strings_thai(self.space)["1"], "「บรรทัดหนึ่ง」")
        self.assertTrue(read_bytes(self.space.strings_csv).startswith(apply.BYTE_ORDER_MARK))

    def test_logs_the_change_with_speaker_and_japanese(self):
        run_quietly(self.space)
        logged = workspace.read_json_lines(self.space.changes_file)
        self.assertEqual(logged, [{
            "chapter": CHAPTER, "idx": "2", "before": "「บรรทัดสอง」",
            "after": "「บรรทัดที่แก้แล้ว」", "rules": ["S1"], "problem": "wrong meaning",
            "speaker": "Yoshino", "jp": "「これは試験です」"}])

    def test_second_apply_changes_nothing(self):
        run_quietly(self.space)
        watched = [self.space.thai_file(CHAPTER), self.space.strings_csv,
                   self.space.changes_file]
        first = [(read_bytes(path), os.stat(path).st_mtime_ns) for path in watched]
        run_quietly(self.space)
        self.assertEqual([(read_bytes(path), os.stat(path).st_mtime_ns) for path in watched],
                         first)
        self.assertEqual(len(workspace.read_json_lines(self.space.changes_file)), 1)

    def test_stale_revision_is_left_alone(self):
        stale = Revision(CHAPTER, "3", "「ข้อความเก่า」", "「ข้อความใหม่」", ("S1",), "stale")
        workspace.write_shapes(self.space.revised_file(CHAPTER), [stale])
        before = read_bytes(self.space.thai_file(CHAPTER))
        run_quietly(self.space)
        self.assertEqual(read_bytes(self.space.thai_file(CHAPTER)), before)
        self.assertEqual(workspace.read_json_lines(self.space.changes_file), [])

    def test_applied_line_closes_its_reviewer_flags(self):
        flags = [Finding(CHAPTER, "2", "S1", "major", "wrong meaning", "reviewer"),
                 Finding(CHAPTER, "3", "S1", "minor", "still open", "reviewer")]
        workspace.write_shapes(self.space.flags_file(CHAPTER), flags)
        run_quietly(self.space)
        self.assertEqual(workspace.read_findings(self.space.flags_file(CHAPTER)), flags[1:])


class NewlineAndByteOrderMark(unittest.TestCase):
    def applied(self, content):
        thai_file, result = apply.apply_revisions(
            CHAPTER, apply.parse_thai_file(content), [REVISION], ["1", "2", "3"])
        return apply.serialize_thai_file(thai_file), result

    def test_unix_newlines_and_byte_order_mark_survive(self):
        content = apply.BYTE_ORDER_MARK + "1\t「บรรทัดหนึ่ง」\n2\t「บรรทัดสอง」\n".encode()
        after, result = self.applied(content)
        self.assertEqual(after, apply.BYTE_ORDER_MARK
                         + "1\t「บรรทัดหนึ่ง」\n2\t「บรรทัดที่แก้แล้ว」\n".encode())
        self.assertEqual(len(result.applied), 1)

    def test_missing_final_newline_survives(self):
        after = self.applied("1\t「บรรทัดหนึ่ง」\r\n2\t「บรรทัดสอง」".encode())[0]
        self.assertEqual(after, "1\t「บรรทัดหนึ่ง」\r\n2\t「บรรทัดที่แก้แล้ว」".encode())

    def test_untranslated_line_is_inserted_in_chapter_order(self):
        missing = Revision(CHAPTER, "2", "", "「บรรทัดใหม่」", ("F3",), "Thai is empty")
        thai_file, result = apply.apply_revisions(
            CHAPTER, apply.parse_thai_file("1\t「หนึ่ง」\r\n3\t「สาม」\r\n".encode()),
            [missing], ["1", "2", "3"])
        self.assertEqual(apply.serialize_thai_file(thai_file),
                         "1\t「หนึ่ง」\r\n2\t「บรรทัดใหม่」\r\n3\t「สาม」\r\n".encode())
        self.assertEqual(len(result.applied), 1)


if __name__ == "__main__":
    unittest.main()
