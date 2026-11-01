#!/usr/bin/env bash
# Assemble the GitHub Pages site into _site/.
# Screenshots live in docs/ (used by README too); copy them in instead of duplicating.
set -euo pipefail
cd "$(dirname "$0")/.."
rm -rf _site
mkdir -p _site/assets/shots _site/assets/installer
cp -r site/. _site/
rm -f _site/build.sh
cp docs/screenshots/*.webp _site/assets/shots/
cp docs/installer-locate.png docs/installer-components.png _site/assets/installer/
touch _site/.nojekyll
echo "built _site/"
