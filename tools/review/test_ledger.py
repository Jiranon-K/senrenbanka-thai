from __future__ import annotations

import contextlib
import io
import tempfile
import unittest

from tools.review import ledger, prompt, reviewer, runner, synthetic
from tools.review.shapes import LedgerEntry
from tools.review.synthetic import CHAPTER, record

MODEL = "claude-sonnet-5-5"
MILLION_EACH = {"input_tokens": 1_000_000, "cache_creation_input_tokens": 1_000_000,
                "cache_read_input_tokens": 1_000_000, "output_tokens": 1_000_000}
SELECTION = runner.Selection((CHAPTER,), False, (), 0)


def unreachable_transport(*arguments, **keywords):
    raise AssertionError("the API must not be called")


def unreachable_key():
    raise AssertionError("the key must not be loaded")


class Prices(unittest.TestCase):
    def test_sync_prices_per_million(self):
        self.assertAlmostEqual(ledger.usage_cost(MODEL, False, MILLION_EACH),
                               2.00 + 2.50 + 0.10 + 10.00)

    def test_batch_halves_everything(self):
        self.assertAlmostEqual(ledger.usage_cost(MODEL, True, MILLION_EACH), 14.60 / 2)

    def test_default_cap(self):
        self.assertEqual(ledger.DEFAULT_CAP_USD, 40.0)

    def test_projection_writes_the_cache_once_then_reads_it(self):
        projection = ledger.project(MODEL, False, 1000, 5, 0, 0)
        self.assertEqual((projection.cache_write_tokens, projection.cache_read_tokens),
                         (1000, 4000))
        self.assertAlmostEqual(projection.usd, (1000 * 2.50 + 4000 * 0.10) / 1_000_000)


class LedgerFile(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.space = synthetic.build_workspace(self.directory.name, [record("「ทดสอบ」")])

    def test_spend_per_stage(self):
        ledger.append_entry(self.space, LedgerEntry("review", "a", MODEL, False,
                                                    {"output_tokens": 1_000_000}))
        ledger.append_entry(self.space, LedgerEntry("revise", "b", MODEL, True,
                                                    {"output_tokens": 1_000_000}))
        entries = ledger.load_entries(self.space)
        self.assertAlmostEqual(ledger.spend(entries), 15.0)
        summary = ledger.stage_summary(entries)
        self.assertTrue(summary[0].startswith("review: 1 requests") and "$10.0000" in summary[0])
        self.assertTrue(summary[1].startswith("revise: 1 requests") and "$5.0000" in summary[1])

    def test_refuses_when_spend_plus_projection_exceeds_the_cap(self):
        projection = ledger.project(MODEL, False, 0, 1, 0, 100_000)
        with self.assertRaises(ledger.CapExceeded):
            ledger.refuse_over_cap(39.5, projection, 40.0)
        ledger.refuse_over_cap(38.0, projection, 40.0)

    def test_submit_over_the_cap_never_reaches_the_api(self):
        ledger.append_entry(self.space, LedgerEntry("review", "spent", MODEL, False,
                                                    {"output_tokens": 4_000_000}))
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(ledger.CapExceeded):
            runner.submit(self.space, reviewer.STAGE, SELECTION, True, ledger.DEFAULT_CAP_USD,
                          unreachable_transport, unreachable_key)
        self.assertIn("projection: 1 requests", output.getvalue())
        self.assertEqual(len(ledger.load_entries(self.space)), 1)

    def test_submit_without_the_rules_file_stops_before_the_api(self):
        with tempfile.TemporaryDirectory() as directory:
            space = synthetic.build_workspace(directory, [record("「ทดสอบ」")], with_rules=False)
            with self.assertRaises(prompt.RulesFileMissing):
                runner.submit(space, reviewer.STAGE, SELECTION, True, ledger.DEFAULT_CAP_USD,
                              unreachable_transport, unreachable_key)


if __name__ == "__main__":
    unittest.main()
