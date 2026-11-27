from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest

PACKAGE_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PACKAGE_DIRECTORY)

import comments


def candidate(source_text, stripped_text):
    return comments.Candidate("sample", comments.Encoded(b"", "\n", source_text), stripped_text)


def proven(language, source_text):
    stripped = language.strip(source_text)
    return comments.proof_problems(candidate(source_text, stripped), language)


class Python(unittest.TestCase):
    def test_comments_removed_and_number_sign_in_string_kept(self):
        source = "#!/usr/bin/env python3\n# -*- coding: utf-8 -*-\n\nHEADER = '# idx\\tth'  # noqa\n"
        self.assertEqual(comments.strip_python(source),
                         "#!/usr/bin/env python3\n\nHEADER = '# idx\\tth'\n")

    def test_docstring_only_body_becomes_pass(self):
        source = 'def greet():\n    """Say hello."""\n\n\ndef leave():\n    """Go."""\n    return 1\n'
        self.assertEqual(comments.strip_python(source),
                         "def greet():\n    pass\n\n\ndef leave():\n    return 1\n")

    def test_module_docstring_and_blank_lines_after_it(self):
        source = '"""Usage text."""\n\nimport os\n\n\n# section\n\ndef run():\n    # why\n\n    return os\n'
        self.assertEqual(comments.strip_python(source),
                         "import os\n\n\ndef run():\n    return os\n")

    def test_multi_line_string_contents_untouched(self):
        source = 'TEXT = """\n# not a comment\n\n\n\nend\n"""\n'
        self.assertEqual(comments.strip_python(source), source)

    def test_proof_accepts_strip_and_rejects_changed_code(self):
        source = 'def greet():\n    """Say hello."""\n    return 1  # one\n'
        self.assertEqual(proven(comments.LANGUAGES[".py"], source), [])
        self.assertEqual(comments.python_proof(candidate(source, "def greet():\n    return 2\n")),
                         ["syntax tree changed"])


class JavaScript(unittest.TestCase):
    def test_strings_urls_templates_and_regex_kept(self):
        source = ("const link = 'https://example.com/#faq'; // trailing\n"
                  "/* block */\n"
                  "const pattern = /\\/\\/[#*]/g;\n"
                  "const text = `a // b ${count /* inner */ + 1} /* c */`;\n"
                  "const ratio = total / 2 // half\n")
        self.assertEqual(comments.strip_javascript(source),
                         "const link = 'https://example.com/#faq';\n"
                         "const pattern = /\\/\\/[#*]/g;\n"
                         "const text = `a // b ${count  + 1} /* c */`;\n"
                         "const ratio = total / 2\n")

    def test_inline_block_comment_keeps_tokens_apart(self):
        self.assertEqual(comments.strip_javascript("return/* gap */value;\n"), "return value;\n")

    def test_block_comment_after_brace_leaves_no_blank_line(self):
        source = "(() => {\n  /* Section:\n     two lines. */\n  run();\n})();\n"
        self.assertEqual(comments.strip_javascript(source), "(() => {\n  run();\n})();\n")

    def test_token_proof_detects_joined_tokens(self):
        proof = comments.token_proof(comments.scan_javascript)
        self.assertEqual(proof(candidate("return/* gap */value;\n", "return value;\n")), [])
        self.assertEqual(proof(candidate("return/* gap */value;\n", "returnvalue;\n")),
                         ["token stream changed"])

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_node_accepts_stripped_source(self):
        source = "const link = 'https://example.com'; // trailing\n"
        self.assertEqual(proven(comments.Language(comments.strip_javascript,
                                                  comments.LANGUAGES[".js"].proofs[:2]), source), [])


class Css(unittest.TestCase):
    def test_comments_removed_strings_and_urls_kept(self):
        source = ("/* header */\n:root {\n  /* Space. */\n  --gap: 4px; /* base */\n"
                  "  content: '/* kept */';\n  background: url(//cdn.example/a.png#x);\n}\n")
        self.assertEqual(comments.strip_css(source),
                         ":root {\n  --gap: 4px;\n  content: '/* kept */';\n"
                         "  background: url(//cdn.example/a.png#x);\n}\n")
        self.assertEqual(comments.token_proof(comments.scan_css)(
            candidate(source, comments.strip_css(source))), [])


class Html(unittest.TestCase):
    def test_comments_removed_attributes_and_scripts_handled(self):
        source = ('<!doctype html>\n<!-- page -->\n<a title="<!-- kept -->" href="#top">x</a>\n'
                  '<script>\n  // inline\n  const link = "//host";\n</script>\n'
                  '<script type="application/ld+json">{"note": "// kept"}</script>\n')
        stripped = comments.strip_html(source)
        self.assertEqual(stripped,
                         '<!doctype html>\n<a title="<!-- kept -->" href="#top">x</a>\n'
                         '<script>\n  const link = "//host";\n</script>\n'
                         '<script type="application/ld+json">{"note": "// kept"}</script>\n')
        self.assertEqual(comments.html_proof(candidate(source, stripped)), [])

    def test_proof_detects_changed_attribute(self):
        self.assertEqual(comments.html_proof(candidate('<a href="#one">x</a>', '<a href="#two">x</a>')),
                         ["tag, attribute or text sequence changed"])


class PowerShell(unittest.TestCase):
    SOURCE = ("#Requires -Version 5\n<#\n.SYNOPSIS\n  help\n#>\nparam([switch]$All) # flag\n"
              "$color = '#ffffff'\n$text = @'\n# not a comment\n'@\n# why\nWrite-Output \"$color # kept\"\n")

    def test_help_and_comments_removed_directive_and_strings_kept(self):
        self.assertEqual(comments.strip_powershell(self.SOURCE),
                         "#Requires -Version 5\nparam([switch]$All)\n"
                         "$color = '#ffffff'\n$text = @'\n# not a comment\n'@\n"
                         "Write-Output \"$color # kept\"\n")

    @unittest.skipUnless(shutil.which("powershell"), "powershell is not installed")
    def test_parser_proof(self):
        self.assertEqual(proven(comments.LANGUAGES[".ps1"], self.SOURCE), [])
        broken = candidate(self.SOURCE, "param([switch]$All)\n$color = '#000000'\n")
        self.assertEqual(comments.powershell_proof(broken), ["token stream changed"])


class Shell(unittest.TestCase):
    SOURCE = ("#!/usr/bin/env bash\n# header\nset -u\n\n# ---- section ----\n"
              "name=\"${1#prefix}\" # trailing\ncount=${#name}; echo \"$# # kept\" '# kept'\n"
              "cat <<EOF\n# heredoc line\nEOF\nvalue=$(echo a#b # inner\n)\necho done\n")

    def test_comments_removed_expansions_and_heredoc_kept(self):
        self.assertEqual(comments.strip_shell(self.SOURCE),
                         "#!/usr/bin/env bash\nset -u\n\n"
                         "name=\"${1#prefix}\"\ncount=${#name}; echo \"$# # kept\" '# kept'\n"
                         "cat <<EOF\n# heredoc line\nEOF\nvalue=$(echo a#b\n)\necho done\n")

    @unittest.skipUnless(shutil.which("bash"), "bash is not installed")
    def test_proof(self):
        self.assertEqual(proven(comments.LANGUAGES[".sh"], self.SOURCE), [])


class Yaml(unittest.TestCase):
    SOURCE = ("# header\nname: ci # trailing\nurl: https://example.com/#faq\ncolor: '#fff'\n"
              "steps:\n  # why\n  - run: |\n      echo # literal\n    name: \"a # b\"\n")

    def test_comments_removed_scalars_kept(self):
        self.assertEqual(comments.strip_yaml(self.SOURCE),
                         "name: ci\nurl: https://example.com/#faq\ncolor: '#fff'\n"
                         "steps:\n  - run: |\n      echo # literal\n    name: \"a # b\"\n")

    @unittest.skipUnless(shutil.which("uv"), "uv is not installed")
    def test_parsed_documents_proof(self):
        self.assertEqual(proven(comments.LANGUAGES[".yml"], self.SOURCE), [])
        self.assertNotEqual(comments.yaml_proof(candidate(self.SOURCE, "name: other\n")), [])


class GitFiles(unittest.TestCase):
    def test_gitignore_comment_lines_removed(self):
        source = "# deny all\n/*\n\n# allow\n!/tools/\n\\#literal\n  # pattern with spaces\n"
        self.assertEqual(comments.strip_gitignore(source),
                         "/*\n\n!/tools/\n\\#literal\n  # pattern with spaces\n")

    def test_gitattributes_comment_lines_removed(self):
        source = "# why\n* text=auto\n\n  # binary\n*.png binary\n"
        self.assertEqual(comments.strip_gitattributes(source), "* text=auto\n\n*.png binary\n")


class Files(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = os.path.join(self.directory.name, "sample.py")

    def write(self, raw):
        with open(self.path, "wb") as sample_file:
            sample_file.write(raw)

    def read(self):
        with open(self.path, "rb") as sample_file:
            return sample_file.read()

    def test_byte_order_mark_and_carriage_returns_preserved(self):
        self.write(b"\xef\xbb\xbf#!/usr/bin/env python3\r\n# note\r\nvalue = 1  # one\r\n")
        self.assertEqual(comments.fix_file(self.path, comments.LANGUAGES[".py"]), [])
        self.assertEqual(self.read(), b"\xef\xbb\xbf#!/usr/bin/env python3\r\nvalue = 1\r\n")

    def test_file_that_fails_its_proof_is_not_written(self):
        raw = b"value = 1  # one\n"
        self.write(raw)
        failing = comments.Language(comments.strip_python, (lambda candidate: ["proof failed"],))
        self.assertEqual(comments.fix_file(self.path, failing), ["proof failed"])
        self.assertEqual(self.read(), raw)

    def test_mixed_line_endings_refused(self):
        raw = b"value = 1  # one\r\nother = 2\n"
        self.write(raw)
        self.assertEqual(comments.fix_file(self.path, comments.LANGUAGES[".py"]),
                         ["ValueError: mixed line endings"])
        self.assertEqual(self.read(), raw)

    def test_clean_file_is_a_fixed_point(self):
        for language, source in ((".py", "value = 1\n\n\n\nother = 2   \n"), (".js", "run();\n\n"),
                                 (".sh", "#!/bin/sh\necho ok\n"), (".yml", "name: ci\n")):
            self.assertEqual(comments.LANGUAGES[language].strip(source), source)


class Scope(unittest.TestCase):
    def test_languages_found_by_suffix_or_name(self):
        self.assertIs(comments.language_for("tools/gui/app.py"), comments.LANGUAGES[".py"])
        self.assertIs(comments.language_for(".gitignore"), comments.LANGUAGES[".gitignore"])
        self.assertIsNone(comments.language_for("README.md"))

    def test_documentation_and_translation_data_are_out_of_scope(self):
        listed = comments.in_scope_files()
        self.assertIn("tools/code_rules/comments.py", listed)
        self.assertEqual([path for path in listed if path.startswith(comments.EXCLUDED_PREFIXES)], [])


if __name__ == "__main__":
    unittest.main()
