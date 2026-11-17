#!/system/bin/sh
# Runs ON THE DEVICE as root. Patches the recovery ramdisk fragment inside a
# stock vendor_boot image and repacks it. Does not write to any partition.
#
# Input:  $WORK/stock.img   (stock vendor_boot of the active slot)
# Output: $WORK/new.img     (patched vendor_boot)
set -e

WORK=${WORK:-/data/local/tmp/jarvis2-recovery}
MAGISK=${MAGISK:-/data/adb/magisk}
MB=$MAGISK/magiskboot
MP=$MAGISK/magiskpolicy

for f in "$MB" "$MP" "$MAGISK/busybox"; do
    [ -x "$f" ] || { echo "missing $f (is Magisk installed?)"; exit 1; }
done
[ -f "$WORK/stock.img" ] || { echo "missing $WORK/stock.img"; exit 1; }

cd "$WORK"
rm -rf unpack verify new.img
mkdir unpack verify

# --- unpack -----------------------------------------------------------------
cd "$WORK/unpack"
# magiskboot exit codes: 0 valid, 1 error, 2 chromeos, 3 vendor_boot
rc=0; "$MB" unpack -h ../stock.img || rc=$?
[ "$rc" = 3 ] || { echo "not a vendor_boot image (magiskboot rc=$rc)"; exit 1; }
C=vendor_ramdisk/recovery.cpio
[ -f "$C" ] || { echo "no 'recovery' ramdisk fragment in vendor_boot"; exit 1; }

mkdir w
"$MB" cpio "$C" \
    "extract prop.default w/prop.default" \
    "extract system/etc/init/hw/init.rc w/init.rc" \
    "extract sepolicy w/sepolicy"

if grep -q '^ro\.debuggable=1$' w/prop.default; then
    echo "this image is already patched; start from a stock vendor_boot"
    exit 3
fi

# --- patch ------------------------------------------------------------------
# adbd keeps root and skips the RSA authorization prompt
sed -i \
    -e 's/^ro\.secure=1$/ro.secure=0/' \
    -e 's/^ro\.adb\.secure=1$/ro.adb.secure=0/' \
    -e 's/^ro\.debuggable=0$/ro.debuggable=1/' \
    w/prop.default
# user builds have no "su" SELinux domain; keep adbd in its own domain
sed -i 's/--root_seclabel=u:r:su:s0/--root_seclabel=u:r:adbd:s0/' w/init.rc
# let the root shell actually do things
"$MP" --load w/sepolicy --save w/sepolicy.new "permissive adbd" "permissive shell"

grep -q '^ro\.secure=0$' w/prop.default
grep -q '^ro\.adb\.secure=0$' w/prop.default
grep -q '^ro\.debuggable=1$' w/prop.default
grep -q 'root_seclabel=u:r:adbd:s0' w/init.rc

"$MB" cpio "$C" \
    "add 0644 prop.default w/prop.default" \
    "add 0644 system/etc/init/hw/init.rc w/init.rc" \
    "add 0644 sepolicy w/sepolicy.new" \
    "add 0755 system/bin/busybox $MAGISK/busybox" \
    "add 0755 system/bin/magiskboot $MB"
rm -rf w

# --- repack -----------------------------------------------------------------
"$MB" repack ../stock.img ../new.img

# --- verify: everything used for a normal boot must be unchanged -------------
cd "$WORK/verify"
rc=0; "$MB" unpack -h ../new.img >/dev/null 2>&1 || rc=$?
[ "$rc" = 3 ] || { echo "VERIFY FAILED: repacked image does not parse"; rm -f ../new.img; exit 2; }
for f in vendor_ramdisk/ramdisk.cpio dtb bootconfig header; do
    [ -f "../unpack/$f" ] || continue
    cmp "../unpack/$f" "$f" || { echo "VERIFY FAILED: $f changed"; rm -f ../new.img; exit 2; }
    echo "unchanged: $f"
done
[ "$(stat -c %s ../new.img)" = "$(stat -c %s ../stock.img)" ] || {
    echo "VERIFY FAILED: image size changed"; rm -f ../new.img; exit 2; }

cd "$WORK"
rm -rf unpack verify
chmod 644 new.img
echo "built $WORK/new.img"
sha256sum new.img
