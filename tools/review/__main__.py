from __future__ import annotations

import argparse
import sys

from . import apply, ledger, lint, prompt, report, reviewer, reviser, runner
from .workspace import repository_workspace


def add_chapter_selection(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--chapter", nargs="+", action="extend", default=[], metavar="NNN")
    group.add_argument("--all", action="store_true")


def add_stage(commands, name: str, with_full: bool) -> None:
    stage_commands = commands.add_parser(name).add_subparsers(dest="action", required=True)
    submit = stage_commands.add_parser("submit")
    submit.add_argument("--chapter", nargs="+", action="extend", default=[], metavar="NNN")
    submit.add_argument("--all", action="store_true")
    if with_full:
        submit.add_argument("--full", nargs="+", action="extend", default=[], metavar="NNN")
    submit.add_argument("--sync", action="store_true")
    submit.add_argument("--cap", type=float, default=ledger.DEFAULT_CAP_USD, metavar="USD")
    submit.add_argument("--limit", type=int, default=0, metavar="REQUESTS")
    stage_commands.add_parser("collect").add_argument("batch_id")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m tools.review")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("lint").add_argument("--chapter", nargs="+", action="extend",
                                             default=[], metavar="NNN")
    add_stage(commands, "review", with_full=False)
    add_stage(commands, "revise", with_full=True)
    add_chapter_selection(commands.add_parser("apply"))
    commands.add_parser("report")
    commands.add_parser("cost")
    return parser


def run_stage(stage: runner.Stage, arguments: argparse.Namespace) -> int:
    workspace = repository_workspace()
    if arguments.action == "collect":
        return runner.collect(workspace, stage, arguments.batch_id)
    full_chapters = tuple(getattr(arguments, "full", []))
    if not (arguments.chapter or arguments.all or full_chapters):
        raise SystemExit("choose --chapter NNN ..., --all or --full NNN ...")
    selection = runner.Selection(tuple(arguments.chapter), arguments.all, full_chapters,
                                 arguments.limit)
    try:
        return runner.submit(workspace, stage, selection, arguments.sync, arguments.cap)
    except (prompt.RulesFileMissing, ledger.CapExceeded) as refusal:
        raise SystemExit(str(refusal))


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    arguments = build_parser().parse_args()
    if arguments.command == "lint":
        return lint.run(repository_workspace(), arguments.chapter)
    if arguments.command == "review":
        return run_stage(reviewer.STAGE, arguments)
    if arguments.command == "revise":
        return run_stage(reviser.STAGE, arguments)
    if arguments.command == "apply":
        return apply.run(repository_workspace(), arguments.chapter, arguments.all)
    if arguments.command == "report":
        return report.run(repository_workspace())
    return ledger.run(repository_workspace())


if __name__ == "__main__":
    sys.exit(main())
