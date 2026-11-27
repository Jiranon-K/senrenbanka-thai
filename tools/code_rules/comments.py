from __future__ import annotations

import argparse
import ast
import contextlib
import fnmatch
import html.parser
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tokenize
from dataclasses import dataclass
from typing import Callable, Iterator

REPOSITORY = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EXCLUDED_PREFIXES = ("docs/", "thai_work/")
SITE_PREFIX = "site/"
SITE_BUILD_INPUTS = ("site", "docs")
SITE_BUILD_SCRIPT = os.path.join("site", "build.py")
SITE_BUILD_OUTPUT = "_site"
BUILD_REPORT = "<build report>"
IGNORE_SAMPLE = (
    ".env",
    "thai_work/strings_cn.csv",
    "thai_work/mt/",
    "tools/gui/ui/bg.png",
    "thai_work/characters.csv",
    "thai_work/th/001.tsv",
    "thai_work/th/001.src.tsv",
)

SENTINEL = "\x00"
BYTE_ORDER_MARK = b"\xef\xbb\xbf"
CODE = "code"
LITERAL = "literal"
COMMENT = "comment"

DOCUMENTABLE = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
SHEBANG = "#!"
TOKEN = re.compile(r"\n|[\w$]+|[^\s\w$]")
JAVASCRIPT_WORD = re.compile(r"[\w$]+")
JAVASCRIPT_REGEX_FLAGS = re.compile(r"[A-Za-z]*")
JAVASCRIPT_WORDS_BEFORE_REGEX = frozenset({
    "return", "typeof", "instanceof", "in", "of", "new", "delete", "void", "throw", "case",
    "do", "else", "yield", "await",
})
JAVASCRIPT_VALUE_ENDINGS = frozenset(")]}")
JAVASCRIPT_VALUE = "value"
JAVASCRIPT_TYPES = frozenset({"text/javascript", "application/javascript", "module"})
SCRIPT_TYPE = re.compile(r"""\stype\s*=\s*["']?([^"'\s>]+)""", re.IGNORECASE)
CSS_UNQUOTED_URL = re.compile(r"url\(\s*(?![\s'\"])", re.IGNORECASE)
HTML_TAG_OPENING = re.compile(r"</?([A-Za-z][^\s/>]*)")
HTML_RAW_TEXT_ELEMENTS = frozenset({"script", "style", "textarea", "title"})
HTML_VERBATIM_ELEMENTS = frozenset({"script", "style", "pre", "textarea"})
POWERSHELL_HERE_STRING_OPENING = re.compile(r"@(['\"])[ \t]*\n")
POWERSHELL_REQUIRES = re.compile(r"#requires\s", re.IGNORECASE)
POWERSHELL_COMMENT_PREDECESSORS = frozenset(" \t\n;({")
SHELL_METACHARACTERS = frozenset(" \t\n;|&()<>")
SHELL_HEREDOC_OPENING = re.compile(r"(?<!<)<<(?!<)(-?)[ \t]*(\\?['\"]?)([\w.+-]+)['\"]?")
YAML_BLOCK_SCALAR_HEADER = re.compile(r"(?:^|\s)[|>][-+0-9]*$")
YAML_KEY_INDENTATION = re.compile(r"[ \t]*(?:-[ \t]+)*")
YAML_QUOTE_PREDECESSORS = frozenset(" \t\n[{,")

POWERSHELL_TOKEN_DUMP = r"""
$text = [IO.File]::ReadAllText($args[0], [Text.Encoding]::UTF8)
$errors = $null
$tokens = [System.Management.Automation.PSParser]::Tokenize($text, [ref]$errors)
$kept = @($tokens | Where-Object { $_.Type -ne 'Comment' -and $_.Type -ne 'NewLine' } |
    ForEach-Object { "$($_.Type) $($_.Content)" })
$report = @{ errors = @($errors).Count; tokens = $kept } | ConvertTo-Json -Compress
[Console]::OpenStandardOutput().Write([Text.Encoding]::UTF8.GetBytes($report), 0,
    [Text.Encoding]::UTF8.GetByteCount($report))
"""

YAML_COMPARISON = """
import sys
import yaml
documents = [list(yaml.safe_load_all(open(path, encoding="utf-8"))) for path in sys.argv[1:3]]
sys.exit(0 if documents[0] == documents[1] else 1)
"""


@dataclass(frozen=True)
class Encoded:
    byte_order_mark: bytes
    line_ending: str
    text: str


@dataclass(frozen=True)
class Removal:
    start: int
    end: int
    replacement: str = ""


@dataclass(frozen=True)
class Segment:
    kind: str
    text: str


@dataclass(frozen=True)
class BlockStyle:
    openers: tuple[str, ...]
    closers: tuple[str, ...]


@dataclass(frozen=True)
class Candidate:
    path: str
    source: Encoded
    stripped: str


@dataclass(frozen=True)
class Language:
    strip: Callable[[str], str]
    proofs: tuple[Callable[[Candidate], list[str]], ...]


@dataclass(frozen=True)
class Heredoc:
    delimiter: str
    strips_tabs: bool


PLAIN = BlockStyle((), ())
BRACES = BlockStyle(("{", "(", "["), ("}", ")", "]"))
INDENTED = BlockStyle((":", "{", "(", "["), ("}", ")", "]"))


def decode(raw: bytes) -> Encoded:
    byte_order_mark = BYTE_ORDER_MARK if raw.startswith(BYTE_ORDER_MARK) else b""
    body = raw[len(byte_order_mark):].decode("utf-8")
    line_ending = "\r\n" if "\r\n" in body else "\n"
    encoded = Encoded(byte_order_mark, line_ending, body.replace("\r\n", "\n"))
    if encode(encoded) != raw:
        raise ValueError("mixed line endings")
    if SENTINEL in body:
        raise ValueError("contains a NUL character")
    return encoded


def encode(encoded: Encoded) -> bytes:
    body = encoded.text.replace("\n", encoded.line_ending)
    return encoded.byte_order_mark + body.encode("utf-8")


def is_removed_line(line: str) -> bool:
    return SENTINEL in line and not line.replace(SENTINEL, "").strip()


def blank_lines_for_gap(gap: list[str], previous_line: str | None, next_line: str | None,
                        style: BlockStyle) -> list[str]:
    removed_positions = [position for position, line in enumerate(gap) if is_removed_line(line)]
    if not removed_positions:
        return gap
    if previous_line is None or next_line is None:
        return []
    if style.openers and previous_line.rstrip().endswith(style.openers):
        return []
    if style.closers and next_line.lstrip().startswith(style.closers):
        return []
    blank_before = removed_positions[0]
    blank_after = len(gap) - 1 - removed_positions[-1]
    return [""] * max(blank_before, blank_after)


def without_sentinel(line: str) -> str:
    return line.replace(SENTINEL, "").rstrip() if SENTINEL in line else line


def settle(marked: str, style: BlockStyle) -> str:
    if SENTINEL not in marked:
        return marked
    ends_with_newline = marked.endswith("\n")
    lines = marked.split("\n")
    if ends_with_newline:
        lines.pop()
    settled: list[str] = []
    gap: list[str] = []
    for line in lines:
        if is_removed_line(line) or not line.strip():
            gap.append(line)
            continue
        kept = without_sentinel(line)
        settled.extend(blank_lines_for_gap(gap, settled[-1] if settled else None, kept, style))
        settled.append(kept)
        gap = []
    settled.extend(blank_lines_for_gap(gap, settled[-1] if settled else None, None, style))
    return "\n".join(settled) + ("\n" if ends_with_newline and settled else "")


def apply_removals(text: str, removals: list[Removal]) -> str:
    pieces = []
    position = 0
    for removal in sorted(removals, key=lambda removal: removal.start):
        pieces.append(text[position:removal.start])
        pieces.append(removal.replacement + SENTINEL)
        position = removal.end
    pieces.append(text[position:])
    return "".join(pieces)


def line_starts(text: str) -> list[int]:
    starts = [0]
    for line in text.split("\n")[:-1]:
        starts.append(starts[-1] + len(line) + 1)
    return starts


def python_comment_removals(text: str) -> list[Removal]:
    starts = line_starts(text)
    removals = []
    for token in tokenize.generate_tokens(io.StringIO(text).readline):
        if token.type != tokenize.COMMENT:
            continue
        if token.start == (1, 0) and token.string.startswith(SHEBANG):
            continue
        removals.append(Removal(starts[token.start[0] - 1] + token.start[1],
                                starts[token.end[0] - 1] + token.end[1]))
    return removals


def has_docstring(node: ast.AST) -> bool:
    if not isinstance(node, DOCUMENTABLE) or not node.body:
        return False
    first = node.body[0]
    return (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str))


def character_offset(lines: list[str], starts: list[int], line_number: int, byte_column: int) -> int:
    line = lines[line_number - 1]
    return starts[line_number - 1] + len(line.encode("utf-8")[:byte_column].decode("utf-8"))


def python_docstring_removals(text: str) -> list[Removal]:
    starts = line_starts(text)
    lines = text.split("\n")
    removals = []
    for owner in ast.walk(ast.parse(text)):
        if not has_docstring(owner):
            continue
        statement = owner.body[0]
        only_statement = len(owner.body) == 1 and not isinstance(owner, ast.Module)
        removals.append(Removal(
            character_offset(lines, starts, statement.lineno, statement.col_offset),
            character_offset(lines, starts, statement.end_lineno, statement.end_col_offset),
            "pass" if only_statement else ""))
    return removals


def strip_python(text: str) -> str:
    removals = python_comment_removals(text) + python_docstring_removals(text)
    return settle(apply_removals(text, removals), INDENTED)


def tree_without_docstrings(text: str) -> ast.AST:
    tree = ast.parse(text)
    for owner in ast.walk(tree):
        if not has_docstring(owner):
            continue
        del owner.body[0]
        if not owner.body and not isinstance(owner, ast.Module):
            owner.body.append(ast.Pass())
    return tree


def python_proof(candidate: Candidate) -> list[str]:
    expected = ast.dump(tree_without_docstrings(candidate.source.text))
    try:
        actual = ast.dump(ast.parse(candidate.stripped))
    except SyntaxError as error:
        return ["stripped source does not parse: %s" % error]
    return [] if actual == expected else ["syntax tree changed"]


class Scanner:
    def __init__(self, text: str) -> None:
        self.text = text
        self.position = 0
        self.segments: list[Segment] = []
        self.code_pieces: list[str] = []

    def at_end(self) -> bool:
        return self.position >= len(self.text)

    def current(self) -> str:
        return self.text[self.position]

    def starts_with(self, prefix: str) -> bool:
        return self.text.startswith(prefix, self.position)

    def previous(self) -> str:
        return self.text[self.position - 1] if self.position else "\n"

    def flush_code(self) -> None:
        if self.code_pieces:
            self.segments.append(Segment(CODE, "".join(self.code_pieces)))
            self.code_pieces = []

    def emit(self, kind: str, length: int) -> str:
        if length <= 0:
            raise ValueError("scanner made no progress at offset %d" % self.position)
        piece = self.text[self.position:self.position + length]
        self.position += len(piece)
        if kind == CODE:
            self.code_pieces.append(piece)
        else:
            self.flush_code()
            self.segments.append(Segment(kind, piece))
        return piece

    def embed(self, segments: list[Segment]) -> None:
        self.flush_code()
        self.segments.extend(segments)
        self.position += sum(len(segment.text) for segment in segments)

    def length_through(self, terminator: str) -> int:
        found = self.text.find(terminator, self.position + 1)
        end = len(self.text) if found < 0 else found + len(terminator)
        return end - self.position

    def length_to_line_end(self) -> int:
        found = self.text.find("\n", self.position)
        return (len(self.text) if found < 0 else found) - self.position

    def quoted_length(self, quote: str, escape: str) -> int:
        index = self.position + 1
        while index < len(self.text):
            if escape and self.text[index] == escape:
                index += 2
            elif self.text.startswith(quote + quote, index) and not escape:
                index += 2
            elif self.text[index] == quote:
                return index + 1 - self.position
            else:
                index += 1
        return len(self.text) - self.position

    def finished(self) -> list[Segment]:
        self.flush_code()
        return self.segments


class JavaScriptScanner(Scanner):
    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.previous_word = ""

    def scan(self) -> list[Segment]:
        if self.starts_with(SHEBANG):
            self.emit(CODE, self.length_to_line_end())
        self.scan_code("")
        return self.finished()

    def scan_code(self, closer: str) -> None:
        depth = 0
        while not self.at_end():
            character = self.current()
            if closer and character == closer and depth == 0:
                return
            depth += {"{": 1, "}": -1}.get(character, 0)
            self.scan_one()

    def scan_one(self) -> None:
        character = self.current()
        if self.starts_with("//"):
            self.emit(COMMENT, self.length_to_line_end())
        elif self.starts_with("/*"):
            self.emit(COMMENT, self.length_through("*/"))
        elif character in "'\"":
            self.emit(LITERAL, self.quoted_length(character, "\\"))
            self.previous_word = JAVASCRIPT_VALUE
        elif character == "`":
            self.scan_template()
        elif character == "/" and self.regex_allowed() and self.regex_length():
            self.emit(LITERAL, self.regex_length())
            self.previous_word = JAVASCRIPT_VALUE
        elif JAVASCRIPT_WORD.match(character):
            self.previous_word = self.emit(CODE, JAVASCRIPT_WORD.match(self.text, self.position).end()
                                           - self.position)
        elif character.isspace():
            self.emit(CODE, 1)
        else:
            self.previous_word = self.emit(CODE, 1)

    def regex_allowed(self) -> bool:
        if self.previous_word in JAVASCRIPT_WORDS_BEFORE_REGEX or not self.previous_word:
            return True
        if self.previous_word == JAVASCRIPT_VALUE or JAVASCRIPT_WORD.match(self.previous_word):
            return False
        return self.previous_word not in JAVASCRIPT_VALUE_ENDINGS

    def regex_length(self) -> int:
        index = self.position + 1
        inside_class = False
        while index < len(self.text) and self.text[index] != "\n":
            character = self.text[index]
            if character == "\\":
                index += 2
                continue
            if character == "/" and not inside_class:
                return JAVASCRIPT_REGEX_FLAGS.match(self.text, index + 1).end() - self.position
            inside_class = character == "[" or (inside_class and character != "]")
            index += 1
        return 0

    def template_text_length(self) -> int:
        index = self.position
        while index < len(self.text) and self.text[index] != "`" and not self.text.startswith("${", index):
            index += 2 if self.text[index] == "\\" else 1
        return min(index, len(self.text)) - self.position

    def scan_template(self) -> None:
        self.emit(LITERAL, 1)
        while not self.at_end() and self.current() != "`":
            if self.starts_with("${"):
                self.emit(CODE, 2)
                self.previous_word = ""
                self.scan_code("}")
                if not self.at_end():
                    self.emit(CODE, 1)
            else:
                self.emit(LITERAL, self.template_text_length())
        if not self.at_end():
            self.emit(LITERAL, 1)
        self.previous_word = JAVASCRIPT_VALUE


class CssScanner(Scanner):
    def scan(self) -> list[Segment]:
        while not self.at_end():
            character = self.current()
            if self.starts_with("/*"):
                self.emit(COMMENT, self.length_through("*/"))
            elif character in "'\"":
                self.emit(LITERAL, self.quoted_length(character, "\\"))
            elif CSS_UNQUOTED_URL.match(self.text, self.position):
                self.emit(LITERAL, self.length_through(")"))
            else:
                self.emit(CODE, 1)
        return self.finished()


class HtmlScanner(Scanner):
    def scan(self) -> list[Segment]:
        while not self.at_end():
            if self.starts_with("<!--"):
                self.emit(COMMENT, self.length_through("-->"))
            elif HTML_TAG_OPENING.match(self.text, self.position):
                self.scan_tag()
            elif self.starts_with("<!") or self.starts_with("<?"):
                self.emit(CODE, self.length_through(">"))
            else:
                self.emit(CODE, 1)
        return self.finished()

    def tag_length(self) -> int:
        index = self.position
        while index < len(self.text) and self.text[index] != ">":
            if self.text[index] in "'\"":
                closing = self.text.find(self.text[index], index + 1)
                index = len(self.text) if closing < 0 else closing
            index += 1
        return min(index + 1, len(self.text)) - self.position

    def scan_tag(self) -> None:
        name = HTML_TAG_OPENING.match(self.text, self.position).group(1).lower()
        tag = self.emit(CODE, self.tag_length())
        if not tag.startswith("</") and name in HTML_RAW_TEXT_ELEMENTS:
            self.scan_raw_text(name, tag)

    def scan_raw_text(self, name: str, tag: str) -> None:
        closing = re.compile("</" + name, re.IGNORECASE).search(self.text, self.position)
        end = closing.start() if closing else len(self.text)
        content = self.text[self.position:end]
        if not content:
            return
        if name == "script" and is_javascript(tag):
            self.embed(JavaScriptScanner(content).scan())
        elif name == "style":
            self.embed(CssScanner(content).scan())
        else:
            self.emit(LITERAL, len(content))


def is_javascript(script_tag: str) -> bool:
    declared = SCRIPT_TYPE.search(script_tag)
    return declared is None or declared.group(1).lower() in JAVASCRIPT_TYPES


class PowerShellScanner(Scanner):
    def scan(self) -> list[Segment]:
        while not self.at_end():
            self.scan_one()
        return self.finished()

    def scan_one(self) -> None:
        character = self.current()
        here_string = POWERSHELL_HERE_STRING_OPENING.match(self.text, self.position)
        if self.starts_with("<#"):
            self.emit(COMMENT, self.length_through("#>"))
        elif here_string:
            self.emit(LITERAL, self.length_through("\n" + here_string.group(1) + "@"))
        elif character == "'":
            self.emit(LITERAL, self.quoted_length("'", ""))
        elif character == '"':
            self.emit(LITERAL, self.quoted_length('"', "`"))
        elif character == "`":
            self.emit(CODE, 2)
        elif character == "#" and self.previous() in POWERSHELL_COMMENT_PREDECESSORS:
            self.scan_number_sign_line()
        else:
            self.emit(CODE, 1)

    def scan_number_sign_line(self) -> None:
        kind = CODE if POWERSHELL_REQUIRES.match(self.text, self.position) else COMMENT
        self.emit(kind, self.length_to_line_end())


class ShellScanner(Scanner):
    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.at_word_start = True
        self.pending_heredocs: list[Heredoc] = []

    def scan(self) -> list[Segment]:
        if self.starts_with(SHEBANG):
            self.emit(CODE, self.length_to_line_end())
        self.scan_code("")
        return self.finished()

    def scan_code(self, closer: str) -> None:
        while not self.at_end():
            if closer and self.current() == closer:
                return
            self.scan_one()

    def scan_one(self) -> None:
        character = self.current()
        starts_word = self.at_word_start
        self.at_word_start = character in SHELL_METACHARACTERS
        heredoc = SHELL_HEREDOC_OPENING.match(self.text, self.position)
        if character == "#" and starts_word:
            self.emit(COMMENT, self.length_to_line_end())
        elif character == "\\":
            self.emit(CODE, 2)
        elif character == "'":
            self.emit(LITERAL, self.length_through("'"))
        elif self.starts_with("$'"):
            self.emit(LITERAL, 1 + self.ansi_quoted_length())
        elif character == '"':
            self.scan_double_quoted()
        elif character == "`":
            self.emit(LITERAL, self.quoted_length("`", "\\"))
        elif self.starts_with("${"):
            self.emit(LITERAL, self.parameter_expansion_length())
        elif character == "(":
            self.scan_parenthesized()
        elif heredoc:
            self.pending_heredocs.append(Heredoc(heredoc.group(3), bool(heredoc.group(1))))
            self.emit(CODE, heredoc.end() - self.position)
        elif character == "\n":
            self.emit(CODE, 1)
            self.scan_heredoc_bodies()
        else:
            self.emit(CODE, 1)

    def ansi_quoted_length(self) -> int:
        index = self.position + 2
        while index < len(self.text) and self.text[index] != "'":
            index += 2 if self.text[index] == "\\" else 1
        return min(index + 1, len(self.text)) - self.position - 1

    def scan_parenthesized(self) -> None:
        self.emit(CODE, 1)
        self.at_word_start = True
        self.scan_code(")")
        if not self.at_end():
            self.emit(CODE, 1)
        self.at_word_start = True

    def scan_double_quoted(self) -> None:
        self.emit(LITERAL, 1)
        while not self.at_end() and self.current() != '"':
            if self.current() == "\\":
                self.emit(LITERAL, 2)
            elif self.starts_with("$("):
                self.emit(CODE, 1)
                self.scan_parenthesized()
            elif self.starts_with("${"):
                self.emit(LITERAL, self.parameter_expansion_length())
            else:
                self.emit(LITERAL, 1)
        if not self.at_end():
            self.emit(LITERAL, 1)
        self.at_word_start = False

    def parameter_expansion_length(self) -> int:
        index = self.position + 2
        depth = 1
        while index < len(self.text) and depth:
            character = self.text[index]
            if character == "\\":
                index += 1
            elif character in "'\"":
                closing = self.text.find(character, index + 1)
                index = len(self.text) if closing < 0 else closing
            elif self.text.startswith("${", index):
                depth += 1
                index += 1
            elif character == "}":
                depth -= 1
            index += 1
        return min(index, len(self.text)) - self.position

    def scan_heredoc_bodies(self) -> None:
        for heredoc in self.pending_heredocs:
            self.scan_heredoc_body(heredoc)
        self.pending_heredocs = []

    def heredoc_body_length(self, heredoc: Heredoc) -> int:
        index = self.position
        while index < len(self.text):
            found = self.text.find("\n", index)
            line_end = len(self.text) if found < 0 else found
            line = self.text[index:line_end]
            index = min(line_end + 1, len(self.text))
            if (line.lstrip("\t") if heredoc.strips_tabs else line) == heredoc.delimiter:
                break
        return index - self.position

    def scan_heredoc_body(self, heredoc: Heredoc) -> None:
        if not self.at_end():
            self.emit(LITERAL, self.heredoc_body_length(heredoc))


class YamlScanner(Scanner):
    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.block_scalar_indentation: int | None = None

    def scan(self) -> list[Segment]:
        while not self.at_end():
            self.scan_line()
        return self.finished()

    def scan_line(self) -> None:
        line = self.text[self.position:self.position + self.length_to_line_end()]
        if self.block_scalar_indentation is not None:
            if not line.strip() or indentation(line) > self.block_scalar_indentation:
                self.emit(LITERAL, min(len(line) + 1, len(self.text) - self.position))
                return
            self.block_scalar_indentation = None
        code = self.scan_line_content()
        if YAML_BLOCK_SCALAR_HEADER.search(code.rstrip()):
            self.block_scalar_indentation = YAML_KEY_INDENTATION.match(line).end()

    def scan_line_content(self) -> str:
        code = []
        while not self.at_end():
            character = self.current()
            if character == "\n":
                self.emit(CODE, 1)
                break
            if character == "#" and self.previous().isspace():
                self.emit(COMMENT, self.length_to_line_end())
            elif character == "'" and self.previous() in YAML_QUOTE_PREDECESSORS:
                self.emit(LITERAL, self.quoted_length("'", ""))
            elif character == '"' and self.previous() in YAML_QUOTE_PREDECESSORS:
                self.emit(LITERAL, self.quoted_length('"', "\\"))
            else:
                code.append(self.emit(CODE, 1))
        return "".join(code)


def indentation(line: str) -> int:
    return len(line) - len(line.lstrip(" \t"))


def comment_replacement(text: str, start: int, end: int) -> str:
    line_prefix = text[text.rfind("\n", 0, start) + 1:start]
    following_line_end = text.find("\n", end)
    line_suffix = text[end:len(text) if following_line_end < 0 else following_line_end]
    if "\n" in text[start:end] and line_prefix.strip() and line_suffix.strip():
        return "\n"
    touches_before = start > 0 and not text[start - 1].isspace()
    touches_after = end < len(text) and not text[end].isspace()
    return " " if touches_before and touches_after else ""


def mark_comments(segments: list[Segment], separates_tokens: bool) -> str:
    text = "".join(segment.text for segment in segments)
    removals = []
    position = 0
    for segment in segments:
        end = position + len(segment.text)
        if segment.kind == COMMENT:
            replacement = comment_replacement(text, position, end) if separates_tokens else ""
            removals.append(Removal(position, end, replacement))
        position = end
    return apply_removals(text, removals)


def token_stream(segments: list[Segment]) -> list[str]:
    tokens: list[str] = []
    for segment in segments:
        if segment.kind == LITERAL:
            found = [segment.text]
        elif segment.kind == COMMENT:
            found = ["\n"] if "\n" in segment.text else []
        else:
            found = TOKEN.findall(segment.text)
        for token in found:
            if token != "\n" or (tokens and tokens[-1] != "\n"):
                tokens.append(token)
    return tokens[:-1] if tokens and tokens[-1] == "\n" else tokens


def strip_javascript(text: str) -> str:
    return settle(mark_comments(JavaScriptScanner(text).scan(), True), BRACES)


def strip_css(text: str) -> str:
    return settle(mark_comments(CssScanner(text).scan(), True), BRACES)


def strip_html(text: str) -> str:
    return settle(mark_comments(HtmlScanner(text).scan(), False), PLAIN)


def strip_powershell(text: str) -> str:
    return settle(mark_comments(PowerShellScanner(text).scan(), True), BRACES)


def strip_shell(text: str) -> str:
    return settle(mark_comments(ShellScanner(text).scan(), True), BRACES)


def strip_yaml(text: str) -> str:
    return settle(mark_comments(YamlScanner(text).scan(), False), PLAIN)


def strip_lines(text: str, is_comment: Callable[[str], bool]) -> str:
    marked = [SENTINEL if is_comment(line) else line for line in text.split("\n")]
    return settle("\n".join(marked), PLAIN)


def strip_gitignore(text: str) -> str:
    return strip_lines(text, lambda line: line.startswith("#"))


def strip_gitattributes(text: str) -> str:
    return strip_lines(text, lambda line: line.lstrip(" \t").startswith("#"))


def run(command: list[str], working_directory: str = REPOSITORY) -> subprocess.CompletedProcess:
    return subprocess.run(command, cwd=working_directory, capture_output=True)


def output_text(completed: subprocess.CompletedProcess) -> str:
    return (completed.stdout + completed.stderr).decode("utf-8", errors="replace").strip()


@contextlib.contextmanager
def temporary_files(contents: list[str], suffix: str) -> Iterator[list[str]]:
    with tempfile.TemporaryDirectory() as directory:
        paths = []
        for number, content in enumerate(contents):
            path = os.path.join(directory, "file%d%s" % (number, suffix)).replace("\\", "/")
            with open(path, "w", encoding="utf-8", newline="") as temporary_file:
                temporary_file.write(content)
            paths.append(path)
        yield paths


def token_proof(scan: Callable[[str], list[Segment]]) -> Callable[[Candidate], list[str]]:
    def proof(candidate: Candidate) -> list[str]:
        before = token_stream(scan(candidate.source.text))
        after = token_stream(scan(candidate.stripped))
        return [] if before == after else ["token stream changed"]
    return proof


def missing_program(program: str) -> list[str]:
    return [] if shutil.which(program) else ["%s is not available to run the proof" % program]


def command_proof(command: list[str], suffix: str) -> Callable[[Candidate], list[str]]:
    def proof(candidate: Candidate) -> list[str]:
        if missing_program(command[0]):
            return missing_program(command[0])
        with temporary_files([candidate.stripped], suffix) as (stripped_path,):
            completed = run(command + [stripped_path])
        if completed.returncode:
            return ["%s failed: %s" % (" ".join(command), output_text(completed))]
        return []
    return proof


def powershell_tokens(script_path: str, source_path: str) -> dict:
    completed = run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                     script_path, source_path])
    return json.loads(completed.stdout.decode("utf-8"))


def powershell_proof(candidate: Candidate) -> list[str]:
    if missing_program("powershell"):
        return missing_program("powershell")
    contents = [POWERSHELL_TOKEN_DUMP, candidate.source.text, candidate.stripped]
    with temporary_files(contents, ".ps1") as (script_path, source_path, stripped_path):
        before = powershell_tokens(script_path, source_path)
        after = powershell_tokens(script_path, stripped_path)
    problems = []
    if after["errors"]:
        problems.append("parser reports %d errors" % after["errors"])
    if before["tokens"] != after["tokens"]:
        problems.append("token stream changed")
    return problems


def yaml_proof(candidate: Candidate) -> list[str]:
    if missing_program("uv"):
        return missing_program("uv")
    contents = [YAML_COMPARISON, candidate.source.text, candidate.stripped]
    with temporary_files(contents, ".txt") as (script_path, source_path, stripped_path):
        completed = run(["uv", "run", "--quiet", "--no-project", "--with", "pyyaml", "python",
                         script_path, source_path, stripped_path])
    if completed.returncode:
        return ["parsed documents changed: %s" % output_text(completed)]
    return []


class HtmlEvents(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.events: list[tuple] = []
        self.verbatim_element = ""

    def handle_starttag(self, tag, attrs):
        self.events.append(("start", tag, tuple(attrs)))
        if tag in HTML_VERBATIM_ELEMENTS:
            self.verbatim_element = tag

    def handle_endtag(self, tag):
        self.events.append(("end", tag))
        if tag == self.verbatim_element:
            self.verbatim_element = ""

    def handle_data(self, data):
        if self.events and self.events[-1][:2] == ("data", self.verbatim_element):
            data = self.events.pop()[2] + data
        self.events.append(("data", self.verbatim_element, data))

    def handle_entityref(self, name):
        self.events.append(("entity", name))

    def handle_charref(self, name):
        self.events.append(("character", name))

    def handle_decl(self, decl):
        self.events.append(("declaration", decl))

    def handle_pi(self, data):
        self.events.append(("instruction", data))

    def unknown_decl(self, data):
        self.events.append(("unknown declaration", data))


def normalized_event(event: tuple) -> tuple:
    if event[0] != "data":
        return event
    element, data = event[1], event[2]
    if element == "script":
        return ("data", element, tuple(token_stream(JavaScriptScanner(data).scan())))
    if element == "style":
        return ("data", element, tuple(token_stream(CssScanner(data).scan())))
    if element:
        return event
    return ("data", element, re.sub(r"\s+", " ", data))


def html_events(text: str) -> list[tuple]:
    recorder = HtmlEvents()
    recorder.feed(text)
    recorder.close()
    return [normalized_event(event) for event in recorder.events]


def html_proof(candidate: Candidate) -> list[str]:
    if html_events(candidate.source.text) == html_events(candidate.stripped):
        return []
    return ["tag, attribute or text sequence changed"]


def stage_site(stage: str) -> None:
    for name in SITE_BUILD_INPUTS:
        shutil.copytree(os.path.join(REPOSITORY, name), os.path.join(stage, name),
                        ignore=shutil.ignore_patterns("__pycache__"))


def built_site(stage: str) -> dict[str, bytes]:
    completed = run([sys.executable, os.path.join(stage, SITE_BUILD_SCRIPT)], stage)
    built = {BUILD_REPORT: b"%d " % completed.returncode + completed.stdout + completed.stderr}
    output = os.path.join(stage, SITE_BUILD_OUTPUT)
    for directory, _, names in os.walk(output):
        for name in names:
            path = os.path.join(directory, name)
            with open(path, "rb") as built_file:
                built[os.path.relpath(path, output).replace("\\", "/")] = built_file.read()
    return built


def site_build_proof(candidate: Candidate) -> list[str]:
    if not candidate.path.startswith(SITE_PREFIX):
        return []
    with tempfile.TemporaryDirectory() as before_stage, tempfile.TemporaryDirectory() as after_stage:
        stage_site(before_stage)
        stage_site(after_stage)
        write_bytes(os.path.join(after_stage, candidate.path), stripped_bytes(candidate))
        before = built_site(before_stage)
        after = built_site(after_stage)
    if not before[BUILD_REPORT].startswith(b"0 "):
        return ["site build fails before stripping"]
    expected = dict(before)
    expected[os.path.basename(candidate.path)] = stripped_bytes(candidate)
    if after == expected:
        return []
    return ["site build output changed beyond the removed comments"]


def git(*arguments: str) -> str:
    completed = run(["git", "-c", "core.quotepath=off", *arguments])
    return completed.stdout.decode("utf-8", errors="replace")


def tracked_files() -> list[str]:
    return [path for path in git("ls-files", "-z").split("\0") if path]


def ignore_decisions() -> list[tuple[str, ...]]:
    fields = git("check-ignore", "-v", "-z", "--non-matching", "--", *IGNORE_SAMPLE).split("\0")
    return [(fields[index], fields[index + 2], fields[index + 3])
            for index in range(0, len(fields) - 3, 4)]


def ignore_snapshot() -> tuple:
    status = git("status", "--porcelain", "--ignored", "-z").split("\0")
    unversioned = sorted(entry for entry in status if entry.startswith(("!! ", "?? ")))
    return (unversioned, tracked_files(), ignore_decisions())


def attribute_sample(text: str) -> list[str]:
    patterns = [line.split()[0] for line in strip_gitattributes(text).split("\n") if line.strip()]
    tracked = tracked_files()
    sample = [pattern.replace("*", "sample").lstrip("/") for pattern in patterns]
    for pattern in patterns:
        sample.extend([path for path in tracked
                       if fnmatch.fnmatch(os.path.basename(path), pattern)][:1])
    return sample


def attribute_snapshot(sample: list[str]) -> str:
    return git("check-attr", "-a", "-z", "--", *sample)


def absolute(path: str) -> str:
    return os.path.join(REPOSITORY, path)


def read_bytes(path: str) -> bytes:
    with open(path, "rb") as source_file:
        return source_file.read()


def write_bytes(path: str, content: bytes) -> None:
    with open(path, "wb") as target_file:
        target_file.write(content)


def stripped_bytes(candidate: Candidate) -> bytes:
    source = candidate.source
    return encode(Encoded(source.byte_order_mark, source.line_ending, candidate.stripped))


def snapshot_with_candidate(candidate: Candidate, snapshot: Callable[[], object]) -> object:
    path = absolute(candidate.path)
    original = read_bytes(path)
    write_bytes(path, stripped_bytes(candidate))
    try:
        return snapshot()
    finally:
        write_bytes(path, original)


def gitignore_proof(candidate: Candidate) -> list[str]:
    before = ignore_snapshot()
    after = snapshot_with_candidate(candidate, ignore_snapshot)
    return [] if before == after else ["ignored, untracked or tracked paths changed"]


def gitattributes_proof(candidate: Candidate) -> list[str]:
    sample = attribute_sample(candidate.source.text)
    before = attribute_snapshot(sample)
    after = snapshot_with_candidate(candidate, lambda: attribute_snapshot(sample))
    return [] if before == after else ["attributes changed"]


def scan_javascript(text: str) -> list[Segment]:
    return JavaScriptScanner(text).scan()


def scan_css(text: str) -> list[Segment]:
    return CssScanner(text).scan()


def scan_shell(text: str) -> list[Segment]:
    return ShellScanner(text).scan()


LANGUAGES = {
    ".py": Language(strip_python, (python_proof,)),
    ".ps1": Language(strip_powershell, (powershell_proof,)),
    ".sh": Language(strip_shell, (token_proof(scan_shell), command_proof(["bash", "-n"], ".sh"))),
    ".js": Language(strip_javascript, (token_proof(scan_javascript),
                                       command_proof(["node", "--check"], ".js"), site_build_proof)),
    ".css": Language(strip_css, (token_proof(scan_css), site_build_proof)),
    ".html": Language(strip_html, (html_proof, site_build_proof)),
    ".yml": Language(strip_yaml, (yaml_proof,)),
    ".yaml": Language(strip_yaml, (yaml_proof,)),
    ".gitignore": Language(strip_gitignore, (gitignore_proof,)),
    ".gitattributes": Language(strip_gitattributes, (gitattributes_proof,)),
}


def language_for(path: str) -> Language | None:
    name = os.path.basename(path)
    return LANGUAGES.get(os.path.splitext(name)[1]) or LANGUAGES.get(name)


def in_scope_files() -> list[str]:
    listed = git("ls-files", "-z", "--cached", "--others", "--exclude-standard").split("\0")
    return sorted({path for path in listed
                   if path and not path.startswith(EXCLUDED_PREFIXES)
                   and language_for(path) and os.path.isfile(absolute(path))})


def candidate_for(path: str, language: Language) -> Candidate:
    source = decode(read_bytes(absolute(path)))
    return Candidate(path, source, language.strip(source.text))


def reading_problem(path: str, language: Language) -> str:
    try:
        candidate_for(path, language)
    except (SyntaxError, tokenize.TokenError, ValueError) as error:
        return "%s: %s" % (type(error).__name__, error)
    return ""


def has_comments(path: str, language: Language) -> bool:
    if reading_problem(path, language):
        return True
    candidate = candidate_for(path, language)
    return candidate.stripped != candidate.source.text


def files_with_comments() -> list[str]:
    return [path for path in in_scope_files() if has_comments(path, language_for(path))]


def proof_problems(candidate: Candidate, language: Language) -> list[str]:
    return [problem for proof in language.proofs for problem in proof(candidate)]


def fix_file(path: str, language: Language) -> list[str]:
    if reading_problem(path, language):
        return [reading_problem(path, language)]
    candidate = candidate_for(path, language)
    problems = proof_problems(candidate, language)
    if not problems:
        write_bytes(absolute(path), stripped_bytes(candidate))
    return problems


def fix() -> int:
    refused = 0
    for path in files_with_comments():
        problems = fix_file(path, language_for(path))
        refused += bool(problems)
        print("refused %s: %s" % (path, "; ".join(problems)) if problems else "rewrote %s" % path)
    return 1 if refused else 0


def check() -> int:
    offenders = files_with_comments()
    for path in offenders:
        print(path)
    if offenders:
        print("%d files still have comments or docstrings; run with --fix" % len(offenders))
    return 1 if offenders else 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m tools.code_rules.comments")
    parser.add_argument("--fix", action="store_true")
    return fix() if parser.parse_args().fix else check()


if __name__ == "__main__":
    sys.exit(main())
