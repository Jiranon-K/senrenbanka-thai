#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mt.py — machine-translate scenario lines JP/EN -> Thai with Claude, one line per idx.

The released patch has 1,744 lines whose Thai belongs to a different JP line
(docs/audit-2026-10.md). This tool cannot produce that defect: every request
asks for a JSON list keyed by `idx`, and a chunk is rejected unless it returns
exactly the idx set it was given, with the same opening quote bracket as the JP.

    python tools/mt.py sync   --csv cn --file 001 [--all]   # direct calls (pilot)
    python tools/mt.py submit --csv cn --file 001 [--all]   # Message Batches, 50% price
    python tools/mt.py collect <batch_id>                   # fetch batch results
    python tools/mt.py wait <batch_id>...                   # block until batches end
    python tools/mt.py merge 001 003 ...                    # mt/cn -> th/<prefix>.tsv
    python tools/mt.py cost                                 # spend so far

--csv cn|r18 picks strings_cn.csv (all-ages) or strings_r18.csv.
Without --all only lines whose `th` is empty are sent; --all retranslates every line.
H scenarios (scenarios.json is_h) are never sent.

Output: thai_work/mt/<csv>/<prefix>.json  {idx: thai}. Nothing in th/ or the
CSVs is touched — review first, then merge.

The key is read from REPO/.env (ANTHROPIC_API_KEY=...), never from the process
environment, so Claude Code keeps using the subscription. Plain urllib on purpose:
the SDK's native dependency (jiter) is blocked by Windows Application Control here.
"""
import os, sys, csv, json, re, time, argparse, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths as P

API = "https://api.anthropic.com/v1"
VERSION = "2026-10-21"
MODEL = "claude-sonnet-5-5"
EFFORT = "medium"
CHUNK = 40          # lines per request
CONTEXT = 6         # preceding lines shown as context only
# USD per 1M tokens for MODEL; the Batches API halves all of them
PRICE = {"input": 2.00, "cache_write": 2.50, "cache_read": 0.20, "output": 10.00}

MT = os.path.join(P.WORK, "mt")
USAGE_LOG = os.path.join(MT, "usage.jsonl")
CSVS = {"cn": P.CSV_CN, "r18": P.CSV_R18}

STYLE = """You translate the Japanese visual novel "Senren＊Banka" (Yuzusoft) into natural, fluent Thai
for a fan patch. You get the Japanese original (authoritative) and the official English
translation (a reference for meaning only — do not translate the English).

Output rules
- Return one Thai line for every input idx, same idx, nothing added or merged. Never move
  content between lines even if a sentence continues on the next line.
- If the JP line starts with 「 『 （ or ( keep the same opening and closing bracket in Thai;
  if it does not, do not add one.
- Drop ruby readings: "[くら]鞍[ま]馬" is just 鞍馬. Drop size/format tags such as "%184;".
  Keep a literal "\\n" only where the JP has one.
- Keep "……", "――", "！？", "♪" style punctuation. Moans, gasps and sound effects become Thai
  onomatopoeia (อ๊ะ, ฮึ่ม, เฮ้อ…), not transliterated Japanese.
- Names and terms: follow the glossary exactly. Honorific さん -> คุณ<name>, 様 -> ท่าน/คุณหนู
  as the glossary says, ちゃん after a name keeps จัง.

Register — match the original, never coarser
- Do NOT use crude Thai (กู, มึง, ไอ้สัตว์, แม่ง, เหี้ย, สัส, ห่า, ตีน, หี, ควย…) unless the
  Japanese is itself vulgar. Ordinary rough male speech (俺/お前, くそ, ちくしょう) is
  ฉัน/นาย/แก, "บ้าเอ๊ย", "ให้ตายสิ" — not กู/มึง.
- Masaomi (narrator and speech): ผม; polite ครับ with elders/strangers, plain นะ/ล่ะ with friends.
  He calls Murasame มุราซาเมะจัง, Yoshino คุณโทโมทาเกะ (later โยชิโนะ), Mako คุณฮิตาจิ (later มาโกะ).
- Murasame: archaic ข้า / เจ้า, calls Masaomi นายท่าน; old-fashioned endings (…นัก, …หรือ, …เถิด).
- Yoshino: ฉัน, polite ค่ะ/คะ, calls him คุณอาริจิ (later มาซาโอมิคุง/มาซาโอมิ when JP changes).
- Mako: ฉัน (ดิฉัน when formal), polite ค่ะ/คะ, calls Yoshino คุณหนูโยชิโนะ, him คุณอาริจิ.
- Lena: หนู or ฉัน with ค่ะ/คะ, slightly odd foreigner phrasing when the JP has it, calls him มาซาโอมิ.
- Koharu: หนู/ฉัน, casual, calls him พี่ชาย and her brother พี่เร็น.
- Roka: ฉัน, casual big-sister tone, calls Masaomi มะบง.
- Rentarou: ฉัน / นาย (แก when teasing), casual ว่ะ/วะ allowed, never กู/มึง.
- Genjuurou (grandfather): stern, ข้า / เจ้า.  Yasuharu: gentle, ผม.  Mizuha: ฉัน, dry.
- Narration lines (no speaker) are Masaomi's inner voice: ผม, plain literary Thai.

Use the preceding-context lines only to understand who is speaking; do not translate them."""


# ─────────────────────────────────────────────────────────────── data

def load_key() -> str:
    env = os.path.join(P.REPO, ".env")
    for line in open(env, encoding="utf-8-sig"):
        if line.startswith("ANTHROPIC_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("ANTHROPIC_API_KEY= not found in " + env)


def glossary_text() -> str:
    rows = list(csv.DictReader(open(P.GLOSSARY, encoding="utf-8-sig")))
    return "\n".join("%s | %s | %s | %s" % (r["jp"], r["en"], r["th"], r["note"]) for r in rows)


def system_blocks() -> list:
    return [{"type": "text",
             "text": STYLE + "\n\nGlossary (jp | en | th | note):\n" + glossary_text(),
             "cache_control": {"type": "ephemeral"}}]


def h_files() -> set:
    return {prefix(s["file"]) for s in json.load(open(P.SCENARIOS, encoding="utf-8")) if s.get("is_h")}


def prefix(name: str) -> str:
    return re.match(r"^\d+[a-z]?", name).group(0)


def load_rows(which: str) -> list:
    return list(csv.DictReader(open(CSVS[which], encoding="utf-8-sig")))


WORDS = re.compile(r"[぀-ヿ一-鿿A-Za-zＡ-Ｚａ-ｚ]")


def is_marker(r: dict) -> bool:
    """Engine rows the CSV carries alongside dialogue (speaker 'face'/'lse', text 'bgm')."""
    return r["speaker_en"] in ("face", "lse") or r["jp"].strip() == "bgm"


def chunks(which: str, files: list, retranslate_all: bool, exclude=()):
    """Yield (custom_id, prefix, context_rows, rows) for every chunk to send."""
    rows = load_rows(which)
    skip = h_files()
    by = {}
    for r in rows:
        by.setdefault(prefix(r["file"]), []).append(r)
    for pf in sorted(by):
        if (files and pf not in files) or pf in exclude:
            continue
        if pf in skip:
            print("skip H scenario", pf)
            continue
        lines = by[pf]
        todo, copied = [], {}
        for i, r in enumerate(lines):
            if is_marker(r) or not (retranslate_all or not r["th"].strip()):
                continue
            if WORDS.search(r["jp"]):
                todo.append(i)
            else:                                   # 「………」 and the like: nothing to translate
                copied[r["idx"]] = re.sub(r"^(%\d+;)+", "", r["jp"].strip())
        if copied:
            save(which, pf, copied)
        for n in range(0, len(todo), CHUNK):
            part = todo[n:n + CHUNK]
            first = part[0]
            ctx = lines[max(0, first - CONTEXT):first]
            yield ("%s-%s-%04d" % (which, pf, n // CHUNK), pf, ctx, [lines[i] for i in part])


def user_message(ctx: list, rows: list) -> str:
    def line(r):
        return {"idx": r["idx"], "speaker": r["speaker_en"], "jp": r["jp"], "en": r["en"]}
    return ("Preceding context (do not translate):\n"
            + json.dumps([line(r) for r in ctx], ensure_ascii=False)
            + "\n\nTranslate these lines:\n"
            + json.dumps([line(r) for r in rows], ensure_ascii=False))


SCHEMA = {
    "type": "object",
    "properties": {"lines": {"type": "array", "items": {
        "type": "object",
        "properties": {"idx": {"type": "string"}, "th": {"type": "string"}},
        "required": ["idx", "th"], "additionalProperties": False}}},
    "required": ["lines"], "additionalProperties": False,
}


def params(ctx, rows) -> dict:
    return {"model": MODEL, "max_tokens": 16000,
            "output_config": {"effort": EFFORT, "format": {"type": "json_schema", "schema": SCHEMA}},
            "system": system_blocks(),
            "messages": [{"role": "user", "content": user_message(ctx, rows)}]}


# ─────────────────────────────────────────────────────────────── checks

OPEN, CLOSE = "「『（(", "」』）)"


def opener(s: str) -> str:
    s = re.sub(r"^(%\d+;|\[[^\]]*\])+", "", s.strip())
    return s[:1] if s[:1] in OPEN else ""


def closer(s: str) -> str:
    s = s.strip()
    return s[-1:] if s[-1:] in CLOSE else ""


def validate(rows: list, out: dict) -> list:
    """Problems that make a chunk unusable. Empty list = accept."""
    want = [r["idx"] for r in rows]
    got = [l["idx"] for l in out.get("lines", [])]
    if sorted(got) != sorted(want):
        return ["idx mismatch: missing %s extra %s" % (sorted(set(want) - set(got)),
                                                       sorted(set(got) - set(want)))]
    th = {l["idx"]: l["th"] for l in out["lines"]}
    bad = []
    for r in rows:
        t = th[r["idx"]]
        if not t.strip():
            bad.append("%s empty" % r["idx"])
        # Only whole-line quotes (dialogue) must keep their brackets; a 『quote』 inside
        # narration may legitimately move when Thai reorders the sentence.
        elif (opener(r["jp"]) and closer(r["jp"])
              and (opener(r["jp"]) != opener(t) or closer(r["jp"]) != closer(t))):
            bad.append("%s brackets %r%r vs %r%r" % (r["idx"], opener(r["jp"]), closer(r["jp"]),
                                                     opener(t), closer(t)))
    return bad


def save(which: str, pf: str, th: dict):
    d = os.path.join(MT, which)
    os.makedirs(d, exist_ok=True)
    f = os.path.join(d, pf + ".json")
    cur = json.load(open(f, encoding="utf-8")) if os.path.exists(f) else {}
    cur.update(th)
    json.dump(cur, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=0)


def log_usage(cid: str, usage: dict, batch: bool):
    os.makedirs(MT, exist_ok=True)
    with open(USAGE_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"id": cid, "batch": batch, "usage": usage}) + "\n")


def text_of(msg: dict) -> str:
    return next((b["text"] for b in msg.get("content", []) if b.get("type") == "text"), "")


def accept(which, pf, rows, msg) -> list:
    if msg.get("stop_reason") != "end_turn":
        return ["stop_reason %s" % msg.get("stop_reason")]
    try:
        out = json.loads(text_of(msg))
    except json.JSONDecodeError as e:
        return ["bad json: %s" % e]
    problems = validate(rows, out)
    if not problems:
        save(which, pf, {l["idx"]: l["th"] for l in out["lines"]})
    return problems


# ─────────────────────────────────────────────────────────────── http

def call(method: str, path: str, body=None, key=None, raw=False):
    req = urllib.request.Request(API + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"content-type": "application/json", "x-api-key": key,
                                          "anthropic-version": VERSION})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                data = r.read()
                return data if raw else json.loads(data)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504, 529) and attempt < 4:
                time.sleep(int(e.headers.get("retry-after") or 2 ** attempt * 5))
                continue
            raise SystemExit("HTTP %d: %s" % (e.code, e.read().decode()[:500]))


# ─────────────────────────────────────────────────────────────── commands

def cmd_sync(a):
    key = load_key()
    jobs = list(chunks(a.csv, a.file, a.all, a.exclude))[:a.limit or None]
    print("%d chunks" % len(jobs))

    def run(job):
        cid, pf, ctx, rows = job
        for attempt in range(2):
            msg = call("POST", "/messages", params(ctx, rows), key)
            log_usage(cid, msg.get("usage", {}), False)
            problems = accept(a.csv, pf, rows, msg)
            if not problems:
                return cid, "ok"
        return cid, "; ".join(problems)

    with ThreadPoolExecutor(4) as ex:
        for cid, status in ex.map(run, jobs):
            print(cid, status)
    cmd_cost(a)


def cmd_submit(a):
    key = load_key()
    jobs = list(chunks(a.csv, a.file, a.all, a.exclude))
    reqs = [{"custom_id": cid, "params": params(ctx, rows)} for cid, pf, ctx, rows in jobs]
    b = call("POST", "/messages/batches", {"requests": reqs}, key)
    os.makedirs(MT, exist_ok=True)
    with open(os.path.join(MT, "batches.jsonl"), "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"id": b["id"], "csv": a.csv, "files": a.file, "all": a.all,
                             "exclude": a.exclude,
                             "chunks": len(reqs)}) + "\n")
    print("batch", b["id"], "with", len(reqs), "chunks:", b["processing_status"])


def cmd_collect(a):
    key = load_key()
    b = call("GET", "/messages/batches/" + a.batch_id, key=key)
    print(b["processing_status"], b["request_counts"])
    if b["processing_status"] != "ended":
        return
    meta = next(json.loads(l) for l in open(os.path.join(MT, "batches.jsonl"), encoding="utf-8")
                if json.loads(l)["id"] == a.batch_id)
    jobs = {cid: (pf, rows) for cid, pf, ctx, rows in chunks(meta["csv"], meta["files"], meta["all"],
                                                                meta.get("exclude", []))}
    retry = []
    for line in call("GET", "/messages/batches/%s/results" % a.batch_id, key=key, raw=True).splitlines():
        res = json.loads(line)
        cid, r = res["custom_id"], res["result"]
        if cid not in jobs:
            continue
        pf, rows = jobs[cid]
        if r["type"] != "succeeded":
            retry.append((cid, r["type"]))
            continue
        log_usage(cid, r["message"].get("usage", {}), True)
        problems = accept(meta["csv"], pf, rows, r["message"])
        if problems:
            retry.append((cid, "; ".join(problems)))
    for cid, why in retry:
        print("RETRY", cid, why)
    print("%d chunks accepted, %d to retry" % (len(jobs) - len(retry), len(retry)))
    cmd_cost(a)


def cmd_merge(a):
    """Write thai_work/mt/cn/<prefix>.json into th/<prefix>.tsv (all-ages only).

    th/ is the translators' source of truth; afterwards run `tsv.py merge` to push
    it into strings_cn.csv and `tsv.py align` to check dialogue/narration shape.
    """
    order = {}
    for r in load_rows("cn"):
        order.setdefault(prefix(r["file"]), []).append(r["idx"])
    for pf in a.prefix:
        new = json.load(open(os.path.join(MT, "cn", pf + ".json"), encoding="utf-8"))
        tsv = os.path.join(P.TH_DIR, pf + ".tsv")
        cur = {}
        if os.path.exists(tsv):
            for line in open(tsv, encoding="utf-8"):
                if line.strip():
                    i, t = line.rstrip("\n").split("\t", 1)
                    cur[i] = t
        before = len(cur)
        cur.update({i: t.replace("\t", " ") for i, t in new.items()})
        with open(tsv, "w", encoding="utf-8") as fh:
            for i in order[pf]:
                if i in cur:
                    fh.write("%s\t%s\n" % (i, cur[i]))
        print("%s: %d lines from mt, %d -> %d in th/" % (pf, len(new), before, len(cur)))


def cmd_wait(a):
    """Block until every listed batch has ended (meant for a background shell)."""
    key = load_key()
    while True:
        states = [call("GET", "/messages/batches/" + b, key=key) for b in a.batch_id]
        print(time.strftime("%H:%M:%S"), [(s["id"][-6:], s["processing_status"], s["request_counts"])
                                         for s in states], flush=True)
        if all(s["processing_status"] == "ended" for s in states):
            return
        time.sleep(120)


def cmd_cost(a=None):
    tot = {"batch": 0.0, "sync": 0.0}
    if not os.path.exists(USAGE_LOG):
        print("no usage yet")
        return
    for l in open(USAGE_LOG, encoding="utf-8"):
        e = json.loads(l)
        u = e["usage"]
        usd = (u.get("input_tokens", 0) * PRICE["input"]
               + u.get("cache_creation_input_tokens", 0) * PRICE["cache_write"]
               + u.get("cache_read_input_tokens", 0) * PRICE["cache_read"]
               + u.get("output_tokens", 0) * PRICE["output"]) / 1e6
        tot["batch" if e["batch"] else "sync"] += usd / 2 if e["batch"] else usd
    print("spent: sync $%.2f  batch $%.2f  total $%.2f" % (tot["sync"], tot["batch"], sum(tot.values())))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("sync", "submit"):
        s = sub.add_parser(name)
        s.add_argument("--csv", choices=CSVS, default="cn")
        s.add_argument("--file", action="append", default=[], help="scenario prefix, e.g. 001")
        s.add_argument("--all", action="store_true", help="retranslate lines that already have Thai")
        s.add_argument("--limit", type=int, default=0, help="send only the first N chunks")
        s.add_argument("--exclude", action="append", default=[], help="scenario prefix to leave out")
    sub.add_parser("collect").add_argument("batch_id")
    sub.add_parser("wait").add_argument("batch_id", nargs="+")
    sub.add_parser("merge").add_argument("prefix", nargs="+")
    sub.add_parser("cost")
    a = ap.parse_args()
    {"sync": cmd_sync, "submit": cmd_submit, "collect": cmd_collect, "wait": cmd_wait, "merge": cmd_merge,
     "cost": cmd_cost}[a.cmd](a)
