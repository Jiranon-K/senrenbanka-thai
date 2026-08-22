#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# test_installer.sh — เทสชุดติดตั้งที่ build_release.py สร้าง แบบจำลอง fresh install
#
#   bash tools/test_installer.sh thai_work/dist/senrenbanka-thai-patch-v1.1
#
# ทำไมต้องมี: install.bat แตะไฟล์เกมหลาย GB ถ้าพลาดคือผู้เล่นเสียไฟล์เกม
# เทสนี้รันได้ทุกครั้งก่อนปล่อย โดยไม่แตะไฟล์เกมจริง
#
# กลไก: ไฟล์ต้นทางในโฟลเดอร์ทดสอบเป็น **hard link** ไปยัง archive ต้นฉบับจริง
#   -> ไม่ต้องก็อป 2 GB, และ `move` ใน install.bat แค่เปลี่ยนชื่อ link
#      ไม่แตะไฟล์จริง (TEST 6 ยืนยันซ้ำว่าต้นฉบับยังไม่เปลี่ยน)
#
# ค่า SHA256 ที่คาดหวังอ่านจาก install.bat ที่ build มา — installer เป็น
# source of truth ไม่ต้อง sync มือ
# ---------------------------------------------------------------------------
set -u

REL="${1:-}"
[ -n "$REL" ] && [ -d "$REL" ] || { echo "ใช้: bash tools/test_installer.sh <โฟลเดอร์ชุดติดตั้ง>"; exit 2; }
REL=$(cd "$REL" && pwd)

REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
G="$REPO"
while [ ! -f "$G/SenrenBanka.exe" ]; do
  parent=$(dirname "$G")
  [ "$parent" = "$G" ] && { echo "หาโฟลเดอร์เกมไม่เจอ (ไม่พบ SenrenBanka.exe)"; exit 2; }
  G="$parent"
done
BASE="$G/_installer_test"

# ---- ดึง SHA256 ที่คาดหวังออกมาจาก install.bat --------------------------------
getset() { sed -n "s/^set \"$1=\([0-9a-f]*\)\".*/\1/p" "$REL/install.bat" | tr -d '\r'; }
O_PATCH=$(getset ORIG_PATCH); T_PATCH=$(getset THAI_PATCH)
O_DATA=$(getset ORIG_DATA);   T_DATA=$(getset THAI_DATA)
O_ADULT=$(getset ORIG_ADULT); T_ADULT=$(getset THAI_ADULT)
[ ${#T_ADULT} = 64 ] || { echo "install.bat ไม่มี THAI_ADULT — build ด้วย adult.xp3.orig ก่อน"; exit 2; }

FAILED=0
chk() { # chk <label> <file> <expected>
  local got; got=$(sha256sum "$2" | cut -d' ' -f1)
  if [ "$got" = "$3" ]; then echo "    PASS  $1"
  else echo "    FAIL  $1"; echo "          want $3"; echo "          got  $got"; FAILED=1; fi
}
hlink() { cmd //c mklink //H "$(cygpath -w "$1")" "$(cygpath -w "$2")" >/dev/null; }

setup() { # setup <dir> <mode:r18|allages>
  rm -rf "$1"; mkdir -p "$1"
  cp "$REL"/* "$1"/
  : > "$1/SenrenBanka.exe"
  hlink "$1/patch.xp3" "$G/patch.xp3.bak"
  hlink "$1/data.xp3"  "$G/data.xp3.bak"
  [ "$2" = r18 ] && hlink "$1/adult.xp3" "$G/adult.xp3.orig"
  return 0
}

# เรียกด้วย path เต็มเสมอ — เครื่องที่ปิด NoDefaultCurrentDirectoryInExePath
# หา .bat ใน current directory ไม่เจอ (เจอจริงตอนเขียนเทสนี้)
run_bat() { ( cd "$1" && cmd //c "$(cygpath -w "$1/$2")" < /dev/null > _log.txt 2>&1; echo $? ) }

# ---------------------------------------------------------------- test 1: R18
echo "=================== TEST 1: R18 mode (patch + data + adult) ==================="
D="$BASE/r18"; setup "$D" r18
RC=$(run_bat "$D" install.bat); echo "  install.bat exit=$RC"
[ "$RC" = 0 ] || { echo "    FAIL  non-zero exit"; FAILED=1; }
chk "patch.xp3  -> thai" "$D/patch.xp3" "$T_PATCH"
chk "data.xp3   -> thai" "$D/data.xp3"  "$T_DATA"
chk "adult.xp3  -> thai" "$D/adult.xp3" "$T_ADULT"
for f in patch data adult; do
  [ -f "$D/$f.xp3.bak" ] || { echo "    FAIL  missing $f.xp3.bak"; FAILED=1; }
done

echo "  -- re-running install.bat (must refuse) --"
RC=$(run_bat "$D" install.bat)
grep -q "SKIP" "$D/_log.txt" && echo "    PASS  refused re-install" || { echo "    FAIL  did not refuse"; FAILED=1; }

echo "  -- uninstall.bat --"
RC=$(run_bat "$D" uninstall.bat); echo "  uninstall.bat exit=$RC"
chk "patch.xp3  -> orig" "$D/patch.xp3" "$O_PATCH"
chk "data.xp3   -> orig" "$D/data.xp3"  "$O_DATA"
chk "adult.xp3  -> orig" "$D/adult.xp3" "$O_ADULT"
ls "$D"/*.bak >/dev/null 2>&1 && { echo "    FAIL  .bak left behind"; FAILED=1; } || echo "    PASS  no .bak left"

# ----------------------------------------------------------- test 2: all-ages
echo
echo "=================== TEST 2: all-ages mode (no adult.xp3) ==================="
D="$BASE/allages"; setup "$D" allages
RC=$(run_bat "$D" install.bat); echo "  install.bat exit=$RC"
[ "$RC" = 0 ] || { echo "    FAIL  non-zero exit"; FAILED=1; }
chk "patch.xp3  -> thai" "$D/patch.xp3" "$T_PATCH"
chk "data.xp3   -> thai" "$D/data.xp3"  "$T_DATA"
[ -f "$D/adult.xp3" ] && { echo "    FAIL  created adult.xp3 out of nowhere"; FAILED=1; } || echo "    PASS  adult.xp3 untouched/absent"
RC=$(run_bat "$D" uninstall.bat)
chk "patch.xp3  -> orig" "$D/patch.xp3" "$O_PATCH"
chk "data.xp3   -> orig" "$D/data.xp3"  "$O_DATA"

# ------------------------------------------------- test 3: wrong adult build
echo
echo "=================== TEST 3: unsupported adult.xp3 build (must abort) ==================="
D="$BASE/badadult"; setup "$D" allages
head -c 1000000 /dev/zero > "$D/adult.xp3"
RC=$(run_bat "$D" install.bat); echo "  install.bat exit=$RC"
[ "$RC" = 1 ] && echo "    PASS  aborted with exit 1" || { echo "    FAIL  expected exit 1"; FAILED=1; }
chk "patch.xp3 untouched" "$D/patch.xp3" "$O_PATCH"
chk "data.xp3  untouched" "$D/data.xp3"  "$O_DATA"
ls "$D"/*.bak >/dev/null 2>&1 && { echo "    FAIL  made a .bak despite aborting"; FAILED=1; } || echo "    PASS  no .bak created"

# ------------------------------------------------------ test 4: missing files
echo
echo "=================== TEST 4: incomplete extraction (must abort) ==================="
D="$BASE/incomplete"; setup "$D" allages
rm -f "$D/thai-data.xdelta"
RC=$(run_bat "$D" install.bat); echo "  install.bat exit=$RC"
[ "$RC" = 1 ] && echo "    PASS  aborted with exit 1" || { echo "    FAIL  expected exit 1"; FAILED=1; }
ls "$D"/*.bak >/dev/null 2>&1 && { echo "    FAIL  made a .bak despite aborting"; FAILED=1; } || echo "    PASS  no .bak created"

# ---------------------------------------------------- test 5: not a game dir
echo
echo "=================== TEST 5: run outside the game folder (must abort) ==================="
D="$BASE/nowhere"; rm -rf "$D"; mkdir -p "$D"; cp "$REL"/* "$D"/
RC=$(run_bat "$D" install.bat); echo "  install.bat exit=$RC"
[ "$RC" = 1 ] && echo "    PASS  aborted with exit 1" || { echo "    FAIL  expected exit 1"; FAILED=1; }

# ------------------------------------- test 6: pristine sources not corrupted
echo
echo "=================== TEST 6: hard-linked originals still pristine ==================="
chk "patch.xp3.bak"  "$G/patch.xp3.bak"  "$O_PATCH"
chk "data.xp3.bak"   "$G/data.xp3.bak"   "$O_DATA"
chk "adult.xp3.orig" "$G/adult.xp3.orig" "$O_ADULT"

rm -rf "$BASE"
echo
if [ "$FAILED" = 0 ]; then echo "########## ALL INSTALLER TESTS PASSED ##########"
else echo "########## SOME TESTS FAILED ##########"; fi
exit $FAILED
