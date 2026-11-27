from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest

from tools.review import ledger, reviewer, reviser, runner, synthetic, workspace
from tools.review.shapes import Finding, Revision
from tools.review.synthetic import CHAPTER, record

USAGE = {"input_tokens": 100, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 50,
         "output_tokens": 20, "output_tokens_details": {"thinking_tokens": 5}}
SELECTION = runner.Selection((CHAPTER,), False, (), 0)
BATCH_ID = "msgbatch_synthetic"


def message(payload):
    return {"stop_reason": "end_turn", "usage": USAGE,
            "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}]}


def quietly(function, *arguments):
    with contextlib.redirect_stdout(io.StringIO()):
        return function(*arguments)


class FakeApi:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def key(self):
        return "synthetic-key"

    def transport(self, method, path, body=None, key=None, raw=False):
        self.calls.append((method, path, body))
        if path == "/messages":
            return message(self.payload)
        if path == "/messages/batches":
            self.custom_ids = [request["custom_id"] for request in body["requests"]]
            return {"id": BATCH_ID, "processing_status": "in_progress"}
        if path.endswith("/results"):
            return "\n".join(json.dumps({"custom_id": custom_id, "result": {
                "type": "succeeded", "message": message(self.payload)}})
                for custom_id in self.custom_ids).encode()
        return {"id": BATCH_ID, "processing_status": "ended", "request_counts": {}}


class StageCase(unittest.TestCase):
    RECORDS = [record("「ขอบคุณค่ะ」", idx="1"), record("「ขอบคุณครับ」", idx="2"),
               record("「สวัสดีค่ะ」", idx="3")]

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.space = synthetic.build_workspace(self.directory.name, self.RECORDS)

    def only_request(self, stage):
        return quietly(stage.select_requests, self.space, SELECTION)[0]


class Chunks(unittest.TestCase):
    def test_forty_records_with_six_of_context(self):
        records = [record("「ทดสอบ」", idx=str(number)) for number in range(1, 96)]
        chunks = runner.chapter_chunks(CHAPTER, records)
        self.assertEqual([len(chunk.records) for chunk in chunks], [40, 40, 15])
        self.assertEqual([chunk.request_id for chunk in chunks],
                         ["900-0000", "900-0001", "900-0002"])
        self.assertEqual(chunks[0].context, ())
        self.assertEqual([context.idx for context in chunks[1].context],
                         ["35", "36", "37", "38", "39", "40"])

    def test_wordless_japanese_is_context_only(self):
        records = [record("……", jp="……", idx="1"), record("「ทดสอบ」", idx="2")]
        chunk = runner.chapter_chunks(CHAPTER, records)[0]
        self.assertEqual([reviewed.idx for reviewed in chunk.records], ["2"])
        self.assertEqual([context.idx for context in chunk.context], ["1"])


class Reviewer(StageCase):
    FLAGS = {"flags": [
        {"idx": "2", "rule": "C1", "severity": "major", "problem": "male particle"},
        {"idx": "77", "rule": "S1", "severity": "minor", "problem": "not in the chunk"}]}

    def test_keeps_flags_in_the_chunk_and_counts_the_rest(self):
        outcome = reviewer.store(self.space, self.only_request(reviewer.STAGE), self.FLAGS)
        self.assertEqual((outcome.accepted, outcome.dropped), (1, 1))
        self.assertEqual(workspace.read_findings(self.space.flags_file(CHAPTER)),
                         [Finding(CHAPTER, "2", "C1", "major", "male particle", "reviewer")])

    def test_storing_again_does_not_duplicate(self):
        request = self.only_request(reviewer.STAGE)
        reviewer.store(self.space, request, self.FLAGS)
        reviewer.store(self.space, request, self.FLAGS)
        self.assertEqual(len(workspace.read_findings(self.space.flags_file(CHAPTER))), 1)

    def test_sync_request_shape_and_ledger(self):
        api = FakeApi(self.FLAGS)
        quietly(runner.submit, self.space, reviewer.STAGE, SELECTION, True, 40.0,
                api.transport, api.key)
        method, path, body = api.calls[0]
        self.assertEqual((method, path, body["model"]), ("POST", "/messages", "claude-sonnet-5-5"))
        self.assertEqual(body["output_config"]["effort"], "medium")
        self.assertEqual(body["output_config"]["format"]["type"], "json_schema")
        self.assertTrue(body["system"][0]["text"].startswith(synthetic.RULES_TEXT))
        self.assertIn("Yoshino | female", body["system"][0]["text"])
        self.assertIn("巫女姫 | Shrine Princess | องค์หญิงมิโกะ", body["system"][0]["text"])
        self.assertIn("\"th\": \"「ขอบคุณครับ」\"", body["messages"][0]["content"])
        entries = ledger.load_entries(self.space)
        self.assertEqual([(entry.stage, entry.request_id, entry.batch, entry.usage)
                          for entry in entries], [("review", "review-900-0000", False, USAGE)])

    def test_unusable_response_is_logged_and_stores_nothing(self):
        api = FakeApi(self.FLAGS)
        api.transport = lambda *arguments, **keywords: {"stop_reason": "max_tokens",
                                                         "usage": USAGE, "content": []}
        quietly(runner.submit, self.space, reviewer.STAGE, SELECTION, True, 40.0,
                api.transport, api.key)
        self.assertEqual(len(ledger.load_entries(self.space)), 1)
        self.assertEqual(workspace.read_findings(self.space.flags_file(CHAPTER)), [])

    def test_batch_collect_is_safe_to_rerun(self):
        api = FakeApi(self.FLAGS)
        quietly(runner.submit, self.space, reviewer.STAGE, SELECTION, False, 40.0,
                api.transport, api.key)
        booked = workspace.read_json_lines(self.space.batches_file)
        self.assertEqual([(entry["id"], entry["stage"], entry["chapters"]) for entry in booked],
                         [(BATCH_ID, "review", [CHAPTER])])
        quietly(runner.collect, self.space, reviewer.STAGE, BATCH_ID, api.transport, api.key)
        quietly(runner.collect, self.space, reviewer.STAGE, BATCH_ID, api.transport, api.key)
        entries = ledger.load_entries(self.space)
        self.assertEqual([(entry.request_id, entry.batch) for entry in entries],
                         [(BATCH_ID + "/review-900-0000", True)])
        self.assertEqual(len(workspace.read_findings(self.space.flags_file(CHAPTER))), 1)


class Reviser(StageCase):
    def test_only_lines_with_findings_are_requested(self):
        request = self.only_request(reviser.STAGE)
        self.assertEqual([(found.idx, found.rule) for found in request.findings], [("2", "C1")])
        self.assertEqual(len(request.chunk.records), 3)

    def test_clean_chapter_sends_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            space = synthetic.build_workspace(directory, [record("「ขอบคุณค่ะ」")])
            self.assertEqual(quietly(reviser.STAGE.select_requests, space, SELECTION), [])

    def test_reviewer_flags_join_the_lint_findings(self):
        workspace.write_shapes(self.space.flags_file(CHAPTER), [
            Finding(CHAPTER, "3", "S1", "major", "wrong meaning", "reviewer")])
        request = self.only_request(reviser.STAGE)
        self.assertEqual([(found.idx, found.rule, found.source) for found in request.findings],
                         [("2", "C1", "lint"), ("3", "S1", "reviewer")])

    def test_full_marks_every_line(self):
        selection = runner.Selection((), False, (CHAPTER,), 0)
        request = quietly(reviser.STAGE.select_requests, self.space, selection)[0]
        self.assertEqual(sorted({found.idx for found in request.findings}), ["1", "2", "3"])
        self.assertEqual([found.rule for found in request.findings if found.idx == "1"],
                         [reviser.FULL_RETRANSLATION])

    def test_line_already_revised_and_waiting_for_apply_is_not_sent_again(self):
        workspace.write_shapes(self.space.revised_file(CHAPTER), [
            Revision(CHAPTER, "2", "「ขอบคุณครับ」", "「ขอบคุณค่ะ」", ("C1",), "male particle")])
        self.assertEqual(quietly(reviser.STAGE.select_requests, self.space, SELECTION), [])

    def test_user_message_attaches_findings_to_their_line(self):
        request = self.only_request(reviser.STAGE)
        body = runner.parameters(reviser.STAGE, "rules", request)
        lines = json.loads(body["messages"][0]["content"].split("\n")[-1])
        self.assertEqual([sorted(line) for line in lines],
                         [["en", "idx", "jp", "speaker", "th"],
                          ["en", "findings", "idx", "jp", "speaker", "th"],
                          ["en", "idx", "jp", "speaker", "th"]])
        self.assertEqual(lines[1]["findings"][0]["rule"], "C1")

    def test_accepts_a_requested_line(self):
        outcome = quietly(reviser.store, self.space, self.only_request(reviser.STAGE),
                          {"lines": [{"idx": "2", "th": "「ขอบคุณค่ะ ๑๒　ครั้ง」"}]})
        self.assertEqual((outcome.accepted, outcome.dropped), (1, 0))
        self.assertEqual(workspace.read_revisions(self.space.revised_file(CHAPTER)), [
            Revision(CHAPTER, "2", "「ขอบคุณครับ」", "「ขอบคุณค่ะ 12 ครั้ง」", ("C1",),
                     "female speaker uses male ครับ")])

    def test_rejects_lines_that_fail_the_form_rules(self):
        request = self.only_request(reviser.STAGE)
        for thai in ("ขอบคุณค่ะ", "「ขอบคุณです」", "  "):
            outcome = quietly(reviser.store, self.space, request,
                              {"lines": [{"idx": "2", "th": thai}]})
            self.assertEqual((outcome.accepted, outcome.dropped), (0, 1), thai)
        self.assertEqual(workspace.read_revisions(self.space.revised_file(CHAPTER)), [])
        self.assertEqual([entry["rules"] for entry
                          in workspace.read_json_lines(self.space.rejected_file)],
                         [["F1"], ["F2"], ["F3"]])

    def test_rejects_a_forbidden_rendering(self):
        with tempfile.TemporaryDirectory() as directory:
            space = synthetic.build_workspace(directory, [
                record("「เรนทาโร่มาแล้วค่ะ」", jp="「廉太郎が来た」")])
            request = quietly(reviser.STAGE.select_requests, space, SELECTION)[0]
            outcome = quietly(reviser.store, space, request,
                              {"lines": [{"idx": "1", "th": "「เร็นทาโรมาแล้วค่ะ」"}]})
            self.assertEqual((outcome.accepted, outcome.dropped), (0, 1))
            outcome = quietly(reviser.store, space, request,
                              {"lines": [{"idx": "1", "th": "「เร็นทาโร่มาแล้วค่ะ」"}]})
            self.assertEqual((outcome.accepted, outcome.dropped), (1, 0))

    def test_ignores_lines_that_were_not_requested(self):
        outcome = quietly(reviser.store, self.space, self.only_request(reviser.STAGE),
                          {"lines": [{"idx": "1", "th": "「เปลี่ยนเอง」"},
                                     {"idx": "88", "th": "「ไม่มีบรรทัดนี้」"}]})
        self.assertEqual((outcome.accepted, outcome.dropped), (0, 2))
        self.assertEqual(workspace.read_revisions(self.space.revised_file(CHAPTER)), [])

    def test_batch_collect_uses_the_findings_recorded_at_submit(self):
        api = FakeApi({"lines": [{"idx": "2", "th": "「ขอบคุณค่ะ」"}]})
        quietly(runner.submit, self.space, reviser.STAGE, SELECTION, False, 40.0,
                api.transport, api.key)
        quietly(runner.collect, self.space, reviser.STAGE, BATCH_ID, api.transport, api.key)
        quietly(runner.collect, self.space, reviser.STAGE, BATCH_ID, api.transport, api.key)
        self.assertEqual([(revision.idx, revision.after, revision.rules) for revision
                          in workspace.read_revisions(self.space.revised_file(CHAPTER))],
                         [("2", "「ขอบคุณค่ะ」", ("C1",))])
        self.assertEqual(len(ledger.load_entries(self.space)), 1)


if __name__ == "__main__":
    unittest.main()
