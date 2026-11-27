from __future__ import annotations

import ast
import os
import tokenize
import unittest

PACKAGE_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
DOCUMENTABLE = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
NAMED = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
COMPREHENSIONS = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)


def sources():
    return [os.path.join(PACKAGE_DIRECTORY, name)
            for name in sorted(os.listdir(PACKAGE_DIRECTORY)) if name.endswith(".py")]


def parsed(source):
    with open(source, encoding="utf-8") as source_file:
        return ast.parse(source_file.read())


def stored_names(tree):
    inside_comprehensions = {id(node) for comprehension in ast.walk(tree)
                             if isinstance(comprehension, COMPREHENSIONS)
                             for node in ast.walk(comprehension)}
    names = [node.id for node in ast.walk(tree)
             if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
             and id(node) not in inside_comprehensions]
    names += [node.arg for node in ast.walk(tree) if isinstance(node, ast.arg)]
    names += [node.name for node in ast.walk(tree) if isinstance(node, NAMED)]
    return names


class CodeRules(unittest.TestCase):
    def test_no_comment_tokens(self):
        for source in sources():
            with open(source, "rb") as source_file:
                comments = [token for token in tokenize.tokenize(source_file.readline)
                            if token.type == tokenize.COMMENT]
            self.assertEqual(comments, [], source)

    def test_no_docstrings(self):
        for source in sources():
            documented = [node for node in ast.walk(parsed(source))
                          if isinstance(node, DOCUMENTABLE)
                          and ast.get_docstring(node) is not None]
            self.assertEqual(documented, [], source)

    def test_no_single_letter_names_outside_comprehensions(self):
        for source in sources():
            short = [name for name in stored_names(parsed(source)) if len(name) < 2]
            self.assertEqual(short, [], source)


if __name__ == "__main__":
    unittest.main()
