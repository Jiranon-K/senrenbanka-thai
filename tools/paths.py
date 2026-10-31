#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TOOLS = os.path.join(REPO, "tools")
WORK = os.path.join(REPO, "thai_work")


CSV_CN = os.path.join(WORK, "strings_cn.csv")
JSON_CN = os.path.join(WORK, "json_cn")
PSB_CN = os.path.join(WORK, "psb_cn")


CSV_R18 = os.path.join(WORK, "strings_r18.csv")
JSON_R18 = os.path.join(WORK, "json_r18")
PSB_R18 = os.path.join(WORK, "psb_r18")


TH_DIR = os.path.join(WORK, "th")
TH_R18_DIR = os.path.join(WORK, "th_r18")
GLOSSARY = os.path.join(WORK, "glossary.csv")

SCENARIOS = os.path.join(WORK, "scenarios.json")
PROGRESS = os.path.join(WORK, "progress.json")
PROGRESS_MD = os.path.join(WORK, "PROGRESS.md")
PROGRESS_R18_MD = os.path.join(WORK, "PROGRESS_R18.md")


FONTS = os.path.join(WORK, "fonts")
FONT_MERGED = os.path.join(FONTS, "Sarabun-merged.ttf")
FONT_VARIANTS = os.path.join(FONTS, "variants")


EXTRACT_DATA = os.path.join(WORK, "dataxp3")
EXTRACT_SCN = os.path.join(WORK, "scnxp3")

DIST = os.path.join(WORK, "dist")


FREEMOTE = os.path.join(TOOLS, "FreeMote")
PSB_DECOMPILE = os.path.join(FREEMOTE, "PsbDecompile.exe")
PSB_BUILD = os.path.join(FREEMOTE, "PsBuild.exe")
XDELTA = os.path.join(TOOLS, "xdelta", "xdelta3.exe")

_GAME_EXE = "SenrenBanka.exe"


def game_dir(start: str | None = None) -> str:
    env = os.environ.get("SBTP_GAME")
    if env:
        if not os.path.isfile(os.path.join(env, _GAME_EXE)):
            raise SystemExit("SBTP_GAME ชี้ไปที่ %s แต่ไม่มี %s อยู่ในนั้น"
                             % (env, _GAME_EXE))
        return os.path.abspath(env)

    d = os.path.abspath(start or REPO)
    while True:
        if os.path.isfile(os.path.join(d, _GAME_EXE)):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            raise SystemExit(
                "หาโฟลเดอร์เกมไม่เจอ — ไต่ขึ้นไปจาก %s แล้วไม่พบ %s\n"
                "ถ้า repo ไม่ได้อยู่ในโฟลเดอร์เกม ให้ตั้ง SBTP_GAME ชี้ไปเอง"
                % (start or REPO, _GAME_EXE))
        d = parent


def game_file(name: str, start: str | None = None) -> str:
    return os.path.join(game_dir(start), name)
