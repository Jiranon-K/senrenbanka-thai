import re
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SITE = REPO / "site"
OUT = REPO / "_site"
SOURCES = {"assets/shots/": REPO / "docs" / "screenshots", "assets/installer/": REPO / "docs"}
REF = re.compile(r"(?<![\w/.-])(?:\./)?(assets/[\w./-]+\.\w+)|/senrenbanka-thai/(assets/[\w./-]+\.\w+)")
TOKEN_USE = re.compile(r"var\(\s*(--[\w-]+)")
TOKEN_DEF = re.compile(r"(?<![\w-])(--[\w-]+)\s*:|@property\s+(--[\w-]+)")
JS_TOKEN = re.compile(r"""['"`](--[\w-]+)['"`]""")


def undefined_tokens() -> set[str]:
    """Custom properties read with var() that nothing declares, sets inline, or sets from JS.

    A typo like var(--shuu) fails silently in CSS (the property just vanishes), so catch it here.
    """
    defined: set[str] = set()
    used: set[str] = set()
    for f in sorted(SITE.iterdir()):
        if f.suffix not in {".css", ".html", ".js"}:
            continue
        text = f.read_text(encoding="utf-8")
        defined.update(a or b for a, b in TOKEN_DEF.findall(text))
        if f.suffix == ".js":
            defined.update(JS_TOKEN.findall(text))
        else:
            used.update(TOKEN_USE.findall(text))
    return used - defined


def main() -> int:
    bad = undefined_tokens()
    if bad:
        print(f"error: var() reads undefined custom properties: {', '.join(sorted(bad))}", file=sys.stderr)
        return 1

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    for f in SITE.iterdir():
        if f.is_file() and f.name != "build.py":
            shutil.copy2(f, OUT / f.name)

    refs = set()
    for f in sorted(SITE.iterdir()):
        if f.suffix in {".html", ".css"}:
            refs.update(a or b for a, b in REF.findall(f.read_text(encoding="utf-8")))
    for ref in sorted(refs):
        prefix = next((p for p in SOURCES if ref.startswith(p)), None)
        src = SOURCES[prefix] / ref[len(prefix):] if prefix else None
        if src is None or not src.is_file():
            print(f"error: {ref} is referenced but missing", file=sys.stderr)
            return 1
        dest = OUT / ref
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)

    (OUT / ".nojekyll").touch()
    print(f"built {OUT.relative_to(REPO)}/ ({len(refs)} assets)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
