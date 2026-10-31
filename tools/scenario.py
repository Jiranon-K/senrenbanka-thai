#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import glob
import os
from dataclasses import dataclass

CN = 2
JP, EN = 0, 1


@dataclass(frozen=True)
class Layout:

    name: str
    slots: tuple[int, ...]
    text_only: bool

    def is_block(self, x) -> bool:
        if not isinstance(x, list) or len(x) not in self.slots:
            return False
        for e in x:
            if not (isinstance(e, list) and len(e) >= 2):
                return False
            if not (e[0] is None or isinstance(e[0], str)):
                return False
            if not isinstance(e[1], str):
                return False
            if self.text_only and not all(v is None or isinstance(v, str) for v in e):
                return False
        return True

    def is_choice(self, x) -> bool:
        lang = x.get("language") if isinstance(x, dict) else None
        return (isinstance(lang, list) and len(lang) in self.slots
                and isinstance(lang[CN], dict) and "text" in lang[CN])

    def blocks(self, node):
        if isinstance(node, list):
            if self.is_block(node):
                yield node
            for e in node:
                yield from self.blocks(e)
        elif isinstance(node, dict):
            for v in node.values():
                yield from self.blocks(v)

    def choices(self, node):
        if isinstance(node, dict):
            if self.is_choice(node):
                yield node
            for v in node.values():
                yield from self.choices(v)
        elif isinstance(node, list):
            for e in node:
                yield from self.choices(e)


ALL_AGES = Layout("all-ages", (4,), text_only=False)
R18 = Layout("r18", (4, 5), text_only=True)


def json_files(d: str) -> list[str]:
    return sorted(p for p in glob.glob(os.path.join(d, "*.ks.json"))
                  if not p.endswith(".resx.json"))
