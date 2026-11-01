import re
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SITE = REPO / "site"
OUT = REPO / "_site"
SOURCES = {"assets/shots/": REPO / "docs" / "screenshots", "assets/installer/": REPO / "docs"}
REF = re.compile(r'(?:src="|url\(")(assets/[^"]+)"')


def main() -> int:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    for f in SITE.iterdir():
        if f.is_file() and f.name != "build.py":
            shutil.copy2(f, OUT / f.name)

    refs = set()
    for name in ("index.html", "styles.css"):
        refs.update(REF.findall((SITE / name).read_text(encoding="utf-8")))
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
