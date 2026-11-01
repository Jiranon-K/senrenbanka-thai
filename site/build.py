"""Assemble the GitHub Pages site into _site/.

Game screenshots stay in docs/screenshots/ (R12) and are copied in here, never
committed under site/. Blocks in index.html wrapped in

    <!-- @requires shots/a.webp shots/b.webp --> ... [<!-- @else --> ...] <!-- @end -->

are kept only when every listed image exists, so a screenshot slot can sit in
the page before its image is added without shipping a broken <img>.

    python site/build.py
"""
import re
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SITE = REPO / "site"
OUT = REPO / "_site"
SHOTS = REPO / "docs" / "screenshots"
INSTALLER = [REPO / "docs" / "installer-locate.png", REPO / "docs" / "installer-components.png"]

BLOCK = re.compile(
    r"[ \t]*<!-- @requires (?P<needs>[^>]+?) -->\n?(?P<body>.*?)"
    r"(?:[ \t]*<!-- @else -->\n?(?P<alt>.*?))?[ \t]*<!-- @end -->\n?",
    re.S,
)


def main() -> int:
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "assets" / "shots").mkdir(parents=True)
    (OUT / "assets" / "installer").mkdir(parents=True)

    for f in SITE.iterdir():
        if f.is_file() and f.name != "build.py":
            shutil.copy2(f, OUT / f.name)
    for f in SHOTS.iterdir():
        if f.suffix.lower() in (".webp", ".png", ".jpg"):
            shutil.copy2(f, OUT / "assets" / "shots" / f.name)
    for f in INSTALLER:
        shutil.copy2(f, OUT / "assets" / "installer" / f.name)
    (OUT / ".nojekyll").touch()

    assets = OUT / "assets"

    def resolve(m: re.Match) -> str:
        needs = m.group("needs").split()
        missing = [n for n in needs if not (assets / n).is_file()]
        print(("skip " if missing else "keep ") + " ".join(needs) + (f"  (missing: {', '.join(missing)})" if missing else ""))
        return (m.group("alt") or "") if missing else m.group("body")

    page = OUT / "index.html"
    html = BLOCK.sub(resolve, page.read_text(encoding="utf-8"))
    if "@requires" in html or "@end" in html:
        print("error: unbalanced @requires/@end block", file=sys.stderr)
        return 1
    for src in re.findall(r'src="(assets/[^"]+)"', html):
        if not (OUT / src).is_file():
            print(f"error: {src} is referenced but missing", file=sys.stderr)
            return 1
    page.write_text(html, encoding="utf-8")
    print(f"built {OUT.relative_to(REPO)}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
