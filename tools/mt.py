#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, sys, csv, json, re, time, argparse, urllib.request, urllib.error
import functools
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths as P
import tsv as tsv_mod

API = "https://api.anthropic.com/v1"
VERSION = "2026-10-21"
MODEL = "claude-sonnet-5-5"
EFFORT = "medium"
CHUNK = 40
CONTEXT = 6
PRICE = {"input": 2.00, "cache_write": 2.50, "cache_read": 0.20, "output": 10.00}

MT = os.path.join(P.WORK, "mt")
USAGE_LOG = os.path.join(MT, "usage.jsonl")
HFLAGS = os.path.join(MT, "hflags_r18.json")
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


def load_key() -> str:
    env = os.path.join(P.REPO, ".env")
    for line in open(env, encoding="utf-8-sig"):
        if line.startswith("ANTHROPIC_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("ANTHROPIC_API_KEY= not found in " + env)


def glossary_text() -> str:
    with open(P.GLOSSARY, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    return "\n".join("%s | %s | %s | %s" % (r["jp"], r["en"], r["th"], r["note"]) for r in rows)


@functools.lru_cache(maxsize=1)
def system_blocks() -> list:
    return [{"type": "text",
             "text": STYLE + "\n\nGlossary (jp | en | th | note):\n" + glossary_text(),
             "cache_control": {"type": "ephemeral"}}]


def h_files() -> set:
    return {prefix(s["file"]) for s in json.load(open(P.SCENARIOS, encoding="utf-8")) if s.get("is_h")}


prefix = tsv_mod.prefix


def load_rows(which: str) -> list:
    return list(csv.DictReader(open(CSVS[which], encoding="utf-8-sig")))


WORDS = re.compile(r"[぀-ヿ一-鿿A-Za-zＡ-Ｚａ-ｚ]")


def is_marker(r: dict) -> bool:
    return r["speaker_en"] in ("face", "lse") or tsv_mod.is_control(r)


def chunks(which: str, files: list, retranslate_all: bool, exclude=()):
    rows = load_rows(which)
    skip = h_files()
    by = {}
    for r in rows:
        by.setdefault(prefix(r["file"]), []).append(r)
    hflags = {k: set(v) for k, v in json.load(open(HFLAGS, encoding="utf-8")).items()} \
        if which == "r18" and os.path.exists(HFLAGS) else {}
    for pf in sorted(by):
        if (files and pf not in files) or pf in exclude:
            continue
        if pf in skip:
            print("skip H scenario", pf)
            continue
        lines = by[pf]
        if which == "r18":
            if pf not in hflags:
                print("skip %s: not classified by hfilter.py" % pf)
                continue
            lines = [r for r in lines if r["idx"] not in hflags[pf]]
        todo, copied = [], {}
        for i, r in enumerate(lines):
            if is_marker(r) or not (retranslate_all or not r["th"].strip()):
                continue
            if WORDS.search(r["jp"]):
                todo.append(i)
            else:
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


OPEN, CLOSE = "「『（(", "」』）)"


def opener(s: str) -> str:
    s = re.sub(r"^(%\d+;|\[[^\]]*\])+", "", s.strip())
    return s[:1] if s[:1] in OPEN else ""


def closer(s: str) -> str:
    s = s.strip()
    return s[-1:] if s[-1:] in CLOSE else ""


def validate(rows: list, out: dict) -> list:
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
        elif KANA_HAN.search(t):
            bad.append("%s kana/kanji left: %r" % (r["idx"], t[:30]))
        elif re.search(r"[฀-๿][A-Za-z]|[A-Za-z][฀-๿]", t.replace("\\n", " ")):
            bad.append("%s latin inside a thai word: %r" % (r["idx"], t[:30]))
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


KEEP_WIDE = set("【】「」『』、。・〜～♪！？（）―…")
KANA_HAN = re.compile(r"[぀-ヺー-ヿ一-鿿]")
THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")


def normalize(t: str) -> str:
    out = []
    for c in t.translate(THAI_DIGITS):
        if c == "　":
            c = " "
        elif 0xFF01 <= ord(c) <= 0xFF5E and c not in KEEP_WIDE:
            c = chr(ord(c) - 0xFEE0)
        out.append(c)
    return "".join(out)


def accept(which, pf, rows, msg) -> list:
    if msg.get("stop_reason") != "end_turn":
        return ["stop_reason %s" % msg.get("stop_reason")]
    try:
        out = json.loads(text_of(msg))
    except json.JSONDecodeError as e:
        return ["bad json: %s" % e]
    for l in out.get("lines", []):
        l["th"] = normalize(l["th"])
    problems = validate(rows, out)
    if not problems:
        save(which, pf, {l["idx"]: l["th"] for l in out["lines"]})
    return problems


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
    order = {}
    for r in load_rows("cn"):
        if not is_marker(r):
            order.setdefault(prefix(r["file"]), []).append(r["idx"])
    for pf in a.prefix:
        new = json.load(open(os.path.join(MT, "cn", pf + ".json"), encoding="utf-8"))
        tsv = os.path.join(P.TH_DIR, pf + ".tsv")
        cur = tsv_mod.read_th(tsv) if os.path.exists(tsv) else {}
        before = len(cur)
        cur.update({i: t.replace("\t", " ") for i, t in new.items()})
        with open(tsv, "w", encoding="utf-8") as fh:
            for i in order[pf]:
                if i in cur:
                    fh.write("%s\t%s\n" % (i, cur[i]))
        print("%s: %d lines from mt, %d -> %d in th/" % (pf, len(new), before, len(cur)))


def cmd_merge_r18(a):
    os.makedirs(P.TH_R18_DIR, exist_ok=True)
    rows = load_rows("r18")
    for pf in a.prefix:
        new = json.load(open(os.path.join(MT, "r18", pf + ".json"), encoding="utf-8"))
        order = [r["idx"] for r in rows if prefix(r["file"]) == pf and r["idx"] in new]
        with open(os.path.join(P.TH_R18_DIR, pf + ".tsv"), "w", encoding="utf-8") as fh:
            for i in order:
                fh.write("%s\t%s\n" % (i, new[i].replace("\t", " ")))
        n = 0
        for r in rows:
            if prefix(r["file"]) == pf and r["idx"] in new and not r["th"].strip():
                r["th"], r["src"] = new[r["idx"]], "TH_R18"
                n += 1
        print("%s: %d lines -> th_r18/%s.tsv, %d filled in strings_r18.csv" % (pf, len(order), pf, n))
    with open(CSVS["r18"], "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def cmd_wait(a):
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
    sub.add_parser("merge-r18").add_argument("prefix", nargs="+")
    sub.add_parser("cost")
    a = ap.parse_args()
    {"sync": cmd_sync, "submit": cmd_submit, "collect": cmd_collect, "wait": cmd_wait, "merge": cmd_merge, "merge-r18": cmd_merge_r18,
     "cost": cmd_cost}[a.cmd](a)
