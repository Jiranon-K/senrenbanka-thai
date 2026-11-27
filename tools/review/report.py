from __future__ import annotations

import collections
import html
from dataclasses import dataclass

from . import apply, history
from .workspace import Workspace

STYLE = """
.review-report { color: var(--foreground); line-height: 1.5; }
.review-report h1 { font-size: 1.25em; margin: 0 0 .5em; }
.review-report h2 { font-size: 1em; margin: 1em 0 .25em; color: var(--muted-foreground); }
.review-report .counts { display: flex; flex-wrap: wrap; gap: .25em .5em; padding: 0;
  margin: 0; list-style: none; }
.review-report .counts li { border: 1px solid var(--border); border-radius: .5em;
  padding: 0 .5em; }
.review-report .counts b { color: var(--accent); }
.review-report .filters { display: flex; flex-wrap: wrap; gap: .75em; margin: 1em 0;
  align-items: center; }
.review-report select { color: inherit; background: var(--card);
  border: 1px solid var(--border); border-radius: .375em; padding: .25em .5em; font: inherit; }
.review-report .change { background: var(--card); border: 1px solid var(--border);
  border-radius: .5em; padding: .75em; margin: 0 0 .75em; }
.review-report .where { display: flex; flex-wrap: wrap; gap: .25em .75em;
  color: var(--muted-foreground); font-size: .875em; }
.review-report .rule { color: var(--accent); border: 1px solid var(--accent);
  border-radius: .375em; padding: 0 .375em; }
.review-report .problem { margin: .375em 0; }
.review-report dl { display: grid; grid-template-columns: minmax(4.5em, max-content) 1fr;
  gap: .25em .75em; margin: 0; }
.review-report dt { color: var(--muted-foreground); font-size: .875em; }
.review-report dd { margin: 0; overflow-wrap: anywhere; }
.review-report .before { text-decoration: line-through;
  text-decoration-color: var(--muted-foreground); color: var(--muted-foreground); }
.review-report .after { border-left: 3px solid var(--accent); padding-left: .5em; }
.review-report [hidden] { display: none; }
"""

SCRIPT = """
(function () {
  var chapter = document.getElementById('review-chapter');
  var rule = document.getElementById('review-rule');
  var shown = document.getElementById('review-shown');
  function refresh() {
    var visible = 0;
    document.querySelectorAll('.review-report .change').forEach(function (change) {
      var rules = change.getAttribute('data-rules').split(' ');
      var keep = (!chapter.value || change.getAttribute('data-chapter') === chapter.value)
        && (!rule.value || rules.indexOf(rule.value) !== -1);
      change.hidden = !keep;
      if (keep) { visible += 1; }
    });
    shown.textContent = visible;
  }
  chapter.addEventListener('change', refresh);
  rule.addEventListener('change', refresh);
  refresh();
})();
"""


@dataclass(frozen=True)
class Change:
    chapter: str
    idx: str
    speaker: str
    rules: tuple
    problem: str
    jp: str
    before: str
    after: str


def current_texts(workspace: Workspace, chapters: set) -> dict[tuple, str]:
    return {(chapter, line.idx): line.text for chapter in sorted(chapters)
            for line in apply.read_thai_file(workspace.thai_file(chapter)).lines if line.idx}


def net_change(line: history.LineHistory, current: str) -> Change:
    leading = history.entries_since_original(line)
    return Change(line.chapter, line.idx, line.speaker,
                  tuple(dict.fromkeys(rule for entry in leading for rule in entry.rules)),
                  "; ".join(dict.fromkeys(entry.problem for entry in leading)),
                  line.jp, line.original, current)


def load_changes(workspace: Workspace) -> list[Change]:
    histories = history.load_histories(workspace)
    current = current_texts(workspace, {chapter for chapter, idx in histories})
    return [net_change(line, current.get(where, "")) for where, line in histories.items()
            if current.get(where, "") != line.original]


def escaped(text: str) -> str:
    return html.escape(text, quote=True)


def count_list(counts: collections.Counter) -> str:
    return "<ul class=\"counts\">%s</ul>" % "".join(
        "<li>%s <b>%d</b></li>" % (escaped(name), count) for name, count in sorted(counts.items()))


def options(label: str, values: list[str]) -> str:
    return "<option value=\"\">%s</option>%s" % (escaped(label), "".join(
        "<option value=\"%s\">%s</option>" % (escaped(value), escaped(value))
        for value in values))


def change_block(change: Change) -> str:
    rules = "".join("<span class=\"rule\">%s</span>" % escaped(rule) for rule in change.rules)
    return ("<article class=\"change\" data-chapter=\"%s\" data-rules=\"%s\">"
            "<div class=\"where\"><span>chapter %s</span><span>idx %s</span><span>%s</span>%s"
            "</div><p class=\"problem\">%s</p><dl>"
            "<dt>Japanese</dt><dd lang=\"ja\">%s</dd>"
            "<dt>Before</dt><dd class=\"before\" lang=\"th\">%s</dd>"
            "<dt>After</dt><dd class=\"after\" lang=\"th\">%s</dd></dl></article>"
            % (escaped(change.chapter), escaped(" ".join(change.rules)),
               escaped(change.chapter), escaped(change.idx),
               escaped(change.speaker or "narration"), rules, escaped(change.problem),
               escaped(change.jp), escaped(change.before), escaped(change.after)))


def render(changes: list[Change]) -> str:
    per_rule = collections.Counter(rule for change in changes for rule in change.rules)
    per_chapter = collections.Counter(change.chapter for change in changes)
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            "<title>Translation review: before and after</title><style>%s</style></head>"
            "<body><div class=\"review-report\"><h1>%d changed lines</h1>"
            "<h2>Per rule</h2>%s<h2>Per chapter</h2>%s"
            "<div class=\"filters\"><select id=\"review-chapter\" aria-label=\"Chapter\">%s"
            "</select><select id=\"review-rule\" aria-label=\"Rule\">%s</select>"
            "<span><span id=\"review-shown\">%d</span> shown</span></div>%s</div>"
            "<script>%s</script></body></html>"
            % (STYLE, len(changes), count_list(per_rule), count_list(per_chapter),
               options("All chapters", sorted(per_chapter)), options("All rules", sorted(per_rule)),
               len(changes), "".join(change_block(change) for change in changes), SCRIPT))


def run(workspace: Workspace) -> int:
    changes = load_changes(workspace)
    with open(workspace.report_file, "w", encoding="utf-8", newline="\n") as report_file:
        report_file.write(render(changes))
    print("%d net changed lines -> %s" % (len(changes), workspace.report_file))
    return 0
