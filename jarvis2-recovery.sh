#!/usr/bin/env bash
# Root-adb recovery for the onn 4K Pro Streaming Device (jarvis2).
# Host-side driver: needs only adb. The device must be bootloader-unlocked
# and rooted with Magisk. See README.md.
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
WORK=/data/local/tmp/jarvis2-recovery
ADB=(adb ${ADB_SERIAL:+-s "$ADB_SERIAL"})

usage() {
    cat <<USAGE
usage: $0 <command>

  build     back up stock vendor_boot, build the patched image (no flashing)
  flash     build, then write the patched image to the active slot
  sideload-enable  add your own signing key so self-signed zips install via sideload
  restore   write the stock backup back to the active slot
  status    show what is currently on the device

env: ADB_SERIAL=<serial>   pick a device
     STOCK_IMG=<file>      use this stock vendor_boot instead of dumping it
     FORCE=1               skip the jarvis2 codename check
USAGE
    exit 1
}

sh_() { "${ADB[@]}" shell "$@" | tr -d '\r'; }
su_() { "${ADB[@]}" shell "su -c '$*'" | tr -d '\r'; }
die() { echo "error: $*" >&2; exit 1; }

preflight() {
    [ "$("${ADB[@]}" get-state 2>/dev/null)" = device ] || die "no device in normal Android (adb get-state != device)"
    local dev; dev=$(sh_ getprop ro.product.device)
    [ "$dev" = jarvis2 ] || [ "${FORCE:-}" = 1 ] || die "device is '$dev', not jarvis2 (FORCE=1 to override)"
    [ "$(su_ id -u)" = 0 ] || die "no root (su failed) - Magisk is required"
    [ "$(sh_ getprop ro.boot.verifiedbootstate)" = orange ] || die "bootloader is not unlocked"
    SLOT=$(sh_ getprop ro.boot.slot_suffix)
    PART=/dev/block/by-name/vendor_boot$SLOT
    BUILD=$(sh_ getprop ro.build.display.id)
    su_ "test -e $PART" || die "$PART not found"
    echo "device: $dev  build: $BUILD  slot: $SLOT"
}

part_sha() { su_ "sha256sum $PART" | cut -c1-64; }

build() {
    su_ "mkdir -p $WORK"
    mkdir -p "$HERE/backup" "$HERE/out"
    local backup="$HERE/backup/vendor_boot${SLOT}-stock-${BUILD}.img" fresh=0

    if [ -n "${STOCK_IMG:-}" ]; then
        echo "using stock image $STOCK_IMG"
        "${ADB[@]}" push "$STOCK_IMG" /data/local/tmp/j2-stock.img >/dev/null
        su_ "mv /data/local/tmp/j2-stock.img $WORK/stock.img"
        [ -f "$backup" ] || cp "$STOCK_IMG" "$backup"
    elif su_ "test -f $WORK/stock.img" && [ -f "$backup" ]; then
        echo "reusing existing stock backup"
    else
        echo "backing up $PART"
        fresh=1
        su_ "cat $PART > $WORK/stock.img"
        "${ADB[@]}" exec-out "su -c 'cat $WORK/stock.img'" > "$backup"
    fi
    [ "$(su_ "sha256sum $WORK/stock.img" | cut -c1-64)" = "$(sha256sum "$backup" | cut -c1-64)" ] \
        || die "host and device stock backups differ"
    echo "stock backup: $backup"

    "${ADB[@]}" push "$HERE/device/build.sh" /data/local/tmp/j2-build.sh >/dev/null
    su_ "mv /data/local/tmp/j2-build.sh $WORK/build.sh"
    if ! "${ADB[@]}" shell "su -c 'WORK=$WORK sh $WORK/build.sh'"; then
        # a backup taken this run from an unusable partition is not a stock backup
        if [ $fresh = 1 ]; then rm -f "$backup"; su_ "rm -f $WORK/stock.img"; fi
        die "build failed"
    fi

    OUT="$HERE/out/vendor_boot${SLOT}-rootadb-${BUILD}.img"
    "${ADB[@]}" exec-out "su -c 'cat $WORK/new.img'" > "$OUT"
    NEW_SHA=$(sha256sum "$OUT" | cut -c1-64)
    [ "$NEW_SHA" = "$(su_ "sha256sum $WORK/new.img" | cut -c1-64)" ] || die "pulled image differs from device copy"
    echo "patched image: $OUT"
}

write_part() {  # $1 = image path on device
    local want; want=$(su_ "sha256sum $1" | cut -c1-64)
    su_ "cat $1 > $PART && sync && echo 3 > /proc/sys/vm/drop_caches"
    [ "$(part_sha)" = "$want" ] || die "READ-BACK MISMATCH on $PART - do not reboot, run '$0 restore'"
    echo "wrote and verified $PART"
}

sideload_enable() {
    local keydir="$HERE/sideload-key"
    [ -f "$keydir/cert.pem" ] || "$HERE/tools/make-sideload-key.sh" "$keydir"
    # pull the stock OTA certs out of the current recovery and merge in our cert
    su_ "mkdir -p $WORK"
    "${ADB[@]}" push "$HERE/device/build.sh" /data/local/tmp/j2-build.sh >/dev/null
    su_ "mv /data/local/tmp/j2-build.sh $WORK/build.sh"
    # need a stock.img first (build() makes the backup and exports stock-otacerts.zip)
    build
    "${ADB[@]}" exec-out "su -c 'cat $WORK/stock-otacerts.zip'" > "$HERE/sideload-key/stock-otacerts.zip"
    python3 "$HERE/tools/build-otacerts.py" "$HERE/sideload-key/stock-otacerts.zip" \
        "$keydir/cert.pem" "$HERE/sideload-key/otacerts.zip"
    "${ADB[@]}" push "$HERE/sideload-key/otacerts.zip" /data/local/tmp/j2-otc.zip >/dev/null
    su_ "mv /data/local/tmp/j2-otc.zip $WORK/otacerts.zip"
    # rebuild now WITH the otacerts injected, then flash
    "${ADB[@]}" shell "su -c 'WORK=$WORK sh $WORK/build.sh'" || die "build failed"
    OUT="$HERE/out/vendor_boot${SLOT}-rootadb-sideload-${BUILD}.img"
    mkdir -p "$HERE/out"; "${ADB[@]}" exec-out "su -c 'cat $WORK/new.img'" > "$OUT"
    write_part "$WORK/new.img"
    cat <<MSG
done. your signing key is in $keydir (keep key.pem private).
sign a zip:   tools/sign-zip.py in.zip out.zip --key $keydir/key.pem --cert $keydir/cert.pem
install it:   adb reboot sideload && adb sideload out.zip
MSG
}

case "${1:-}" in
build)
    preflight; build ;;
flash)
    preflight; build
    write_part "$WORK/new.img"
    echo "done. test with: adb reboot recovery && adb shell id" ;;
sideload-enable)
    preflight; sideload_enable ;;
restore)
    preflight
    su_ "test -f $WORK/stock.img" || {
        b=$(ls "$HERE"/backup/vendor_boot"${SLOT}"-stock-*.img 2>/dev/null | head -1)
        [ -n "$b" ] || die "no stock backup on device or in $HERE/backup"
        su_ "mkdir -p $WORK"
        "${ADB[@]}" push "$b" /data/local/tmp/j2-stock.img >/dev/null
        su_ "mv /data/local/tmp/j2-stock.img $WORK/stock.img"
    }
    write_part "$WORK/stock.img" ;;
status)
    preflight
    cur=$(part_sha); echo "vendor_boot$SLOT sha256: $cur"
    for f in stock new; do
        s=$(su_ "sha256sum $WORK/$f.img 2>/dev/null" | cut -c1-64)
        [ -n "$s" ] && [ "$s" = "$cur" ] && echo "=> matches $WORK/$f.img ($f)"
    done ;;
*) usage ;;
esac
