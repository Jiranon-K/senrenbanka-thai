from __future__ import annotations

import json
import tempfile
import unittest

from tools.review import arbiter, ledger, runner, synthetic, workspace
from tools.review.shapes import Arbitration, Contest
from tools.review.synthetic import CHAPTER, record
from tools.review.test_stages import BATCH_ID, SELECTION, FakeApi, quietly

ORIGINAL_TEXT = "「ข้อความเดิม」"
CURRENT_TEXT = "「ข้อความใหม่」"


def log_change(space, idx, before, after):
    workspace.append_json_line(space.changes_file, {
        "chapter": CHAPTER, "idx": idx, "before": before, "after": after, "rules": ["S1"],
        "problem": "wrong meaning", "speaker": "Yoshino", "jp": "「これは試験です」"})


def label_of_current(idx):
    return "Y" if arbiter.original_label(CHAPTER, idx) == "X" else "X"


class Assignment(unittest.TestCase):
    def test_label_is_stable_and_uses_both_positions(self):
        labels = [arbiter.original_label(CHAPTER, str(number)) for number in range(200)]
        self.assertEqual(labels, [arbiter.original_label(CHAPTER, str(number))
                                  for number in range(200)])
        self.assertEqual(arbiter.original_label("114", "7"), arbiter.original_label("114", "7"))
        self.assertGreater(labels.count("X"), 60)
        self.assertGreater(labels.count("Y"), 60)

    def test_candidates_follow_the_label(self):
        for number in range(20):
            contest = Contest(record(CURRENT_TEXT, idx=str(number)), (), ORIGINAL_TEXT)
            shown = arbiter.candidates(contest)
            label = arbiter.original_label(CHAPTER, str(number))
            self.assertEqual(shown[label], ORIGINAL_TEXT)
            self.assertEqual(sorted(shown.values()), sorted([ORIGINAL_TEXT, CURRENT_TEXT]))

    def test_choice_resolves_back_to_the_candidate(self):
        for number in range(20):
            idx = str(number)
            label = arbiter.original_label(CHAPTER, idx)
            self.assertEqual(arbiter.verdict_for(CHAPTER, idx, label), "original")
            self.assertEqual(arbiter.verdict_for(CHAPTER, idx, label_of_current(idx)),
                             "current")
            self.assertEqual(arbiter.verdict_for(CHAPTER, idx, "same"), "same")


class Arbiter(unittest.TestCase):
    RECORDS = [record("「บรรทัดหนึ่ง」", idx="1"), record(CURRENT_TEXT, idx="2"),
               record("「บรรทัดสาม」", idx="3"), record("「บรรทัดสี่」", idx="4"),
               record(CURRENT_TEXT, idx="5"), record(ORIGINAL_TEXT, idx="6")]

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.space = synthetic.build_workspace(self.directory.name, self.RECORDS)
        log_change(self.space, "2", ORIGINAL_TEXT, "「ข้อความกลาง」")
        log_change(self.space, "2", "「ข้อความกลาง」", CURRENT_TEXT)
        log_change(self.space, "5", ORIGINAL_TEXT, CURRENT_TEXT)
        log_change(self.space, "6", ORIGINAL_TEXT, CURRENT_TEXT)

    def only_request(self):
        requests = quietly(arbiter.STAGE.select_requests, self.space, SELECTION)
        self.assertEqual(len(requests), 1)
        return requests[0]

    def test_only_lines_that_differ_from_their_original_are_contested(self):
        request = self.only_request()
        self.assertEqual([(contest.record.idx, contest.original, contest.record.th)
                          for contest in request.contests],
                         [("2", ORIGINAL_TEXT, CURRENT_TEXT), ("5", ORIGINAL_TEXT, CURRENT_TEXT)])
        self.assertEqual([[context.idx for context in contest.preceding]
                          for contest in request.contests], [["1"], ["2", "3", "4"]])

    def test_request_sends_candidates_and_no_english(self):
        body = runner.parameters(arbiter.STAGE, "rules", self.only_request())
        content = body["messages"][0]["content"]
        lines = json.loads(content.split("\n")[-1])
        self.assertEqual([sorted(line) for line in lines],
                         [["X", "Y", "context", "idx", "jp", "speaker"]] * 2)
        self.assertEqual(sorted(lines[1]["context"][0]), ["jp", "speaker", "th"])
        self.assertNotIn("This is a test.", content)
        self.assertNotIn("\"en\"", content)
        self.assertEqual(body["system"][1]["text"], arbiter.STAGE.role)
        self.assertEqual(body["output_config"]["format"]["schema"]["properties"]["choices"]
                         ["items"]["properties"]["better"]["enum"], ["X", "Y", "same"])

    def test_chunks_hold_at_most_forty_lines(self):
        contests = [Contest(record(CURRENT_TEXT, idx=str(number)), (), ORIGINAL_TEXT)
                    for number in range(95)]
        requests = arbiter.chapter_requests(self.space, CHAPTER, contests)
        self.assertEqual([len(request.contests) for request in requests], [40, 40, 15])
        self.assertEqual([request.chunk.request_id for request in requests],
                         ["900-0000", "900-0001", "900-0002"])

    def test_store_resolves_labels_and_drops_unrequested_choices(self):
        outcome = arbiter.store(self.space, self.only_request(), {"choices": [
            {"idx": "2", "better": arbiter.original_label(CHAPTER, "2"), "reason": "meaning"},
            {"idx": "6", "better": "X", "reason": "not requested"},
            {"idx": "77", "better": "Y", "reason": "not in the chapter"}]})
        self.assertEqual((outcome.accepted, outcome.dropped), (1, 2))
        self.assertEqual(outcome.detail,
                         "1 original, 0 current, 0 same, 2 not requested, 1 not returned")
        self.assertEqual(workspace.read_arbitrations(self.space.arbitration_file(CHAPTER)), [
            Arbitration(CHAPTER, "2", ORIGINAL_TEXT, CURRENT_TEXT, "original", "meaning")])

    def test_judged_lines_are_not_sent_again_until_their_text_changes(self):
        request = self.only_request()
        arbiter.store(self.space, request, {"choices": [
            {"idx": "2", "better": "same", "reason": "equal"},
            {"idx": "5", "better": label_of_current("5"), "reason": "meaning"}]})
        self.assertEqual(quietly(arbiter.STAGE.select_requests, self.space, SELECTION), [])
        self.assertEqual([stored.verdict for stored in workspace.read_arbitrations(
            self.space.arbitration_file(CHAPTER))], ["same", "current"])

    def test_sync_run_writes_the_ledger_under_its_stage(self):
        api = FakeApi({"choices": [{"idx": "5", "better": "same", "reason": "equal"}]})
        quietly(runner.submit, self.space, arbiter.STAGE, SELECTION, True, 40.0,
                api.transport, api.key)
        self.assertEqual([(entry.stage, entry.request_id) for entry
                          in ledger.load_entries(self.space)],
                         [("arbitrate", "arbitrate-900-0000")])

    def test_cap_refuses_before_any_request(self):
        api = FakeApi({"choices": []})
        with self.assertRaises(ledger.CapExceeded):
            quietly(runner.submit, self.space, arbiter.STAGE, SELECTION, True, 0.0,
                    api.transport, api.key)
        self.assertEqual(api.calls, [])

    def test_batch_collect_uses_the_contests_recorded_at_submit(self):
        api = FakeApi({"choices": [
            {"idx": "5", "better": arbiter.original_label(CHAPTER, "5"), "reason": "meaning"}]})
        quietly(runner.submit, self.space, arbiter.STAGE, SELECTION, False, 40.0,
                api.transport, api.key)
        quietly(runner.collect, self.space, arbiter.STAGE, BATCH_ID, api.transport, api.key)
        quietly(runner.collect, self.space, arbiter.STAGE, BATCH_ID, api.transport, api.key)
        self.assertEqual(workspace.read_arbitrations(self.space.arbitration_file(CHAPTER)), [
            Arbitration(CHAPTER, "5", ORIGINAL_TEXT, CURRENT_TEXT, "original", "meaning")])
        self.assertEqual(len(ledger.load_entries(self.space)), 1)


if __name__ == "__main__":
    unittest.main()
