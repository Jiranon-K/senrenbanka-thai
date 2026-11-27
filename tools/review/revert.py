from __future__ import annotations

import os

from . import apply
from . import workspace as workspace_module
from .shapes import ORIGINAL, Arbitration, Record, Revision
from .workspace import Workspace

ARBITER_RULE = "ARB"
ARBITER_PROBLEM = "arbiter preferred the original"


def reversal(arbitration: Arbitration) -> Revision:
    return Revision(arbitration.chapter, arbitration.idx, arbitration.current,
                    arbitration.original, (ARBITER_RULE,), ARBITER_PROBLEM)


def chapter_reversals(workspace: Workspace, chapter: str) -> list[Revision]:
    return [reversal(arbitration) for arbitration
            in workspace_module.read_arbitrations(workspace.arbitration_file(chapter))
            if arbitration.verdict == ORIGINAL]


def log_reversals(workspace: Workspace, reverted: tuple, records: dict) -> None:
    for revision in reverted:
        workspace_module.append_json_line(
            workspace.changes_file, apply.change_fields(revision, records[revision.idx]))


def withdraw_revisions(workspace: Workspace, chapter: str, reverted: set) -> None:
    path = workspace.revised_file(chapter)
    revisions = workspace_module.read_revisions(path)
    remaining = [revision for revision in revisions if revision.idx not in reverted]
    if len(remaining) != len(revisions):
        workspace_module.write_shapes(path, remaining)


def revert_chapter(workspace: Workspace, chapter: str,
                   records: list[Record]) -> apply.ChapterResult:
    path = workspace.thai_file(chapter)
    after, result = apply.apply_revisions(
        chapter, apply.read_thai_file(path), chapter_reversals(workspace, chapter),
        [record.idx for record in records])
    if result.applied:
        apply.write_thai_file(path, after)
        log_reversals(workspace, result.applied, {record.idx: record for record in records})
        withdraw_revisions(workspace, chapter, {revision.idx for revision in result.applied})
    return result


def arbitrated_chapters(workspace: Workspace) -> list[str]:
    return workspace_module.stored_chapters(
        os.path.dirname(workspace.arbitration_file("")))


def run(workspace: Workspace, chapters: list[str], everything: bool) -> int:
    grouped = workspace_module.group_by_chapter(workspace_module.load_records(workspace))
    wanted = arbitrated_chapters(workspace) if everything else chapters
    results = [revert_chapter(workspace, chapter, grouped.get(chapter, []))
               for chapter in wanted]
    mirrored = apply.mirror_into_strings(workspace, wanted)
    print("reverted %d, already reverted %d, stale %d (Thai changed since the arbitration); "
          "%d rows updated in %s"
          % (sum(len(result.applied) for result in results),
             sum(result.already_applied for result in results),
             sum(result.stale for result in results), mirrored, workspace.strings_csv))
    return 0
