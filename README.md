# jarvis2-recovery

Root-adb recovery for the **onn 4K Pro Streaming Device** (codename `jarvis2`,
Amlogic S905X5M, Android 14).

This project patches the stock recovery to provide a root ADB shell with
`busybox` and `magiskboot`. Recovery ADB currently accepts USB hosts without
authorization. Anyone with USB access while recovery is running can use that
root shell.

By default, sideload uses the manufacturer's signing certificates. The optional
sideload setup adds a certificate for packages you sign yourself.

## Installation guide

Follow the [Linux and Windows recovery runbook](docs/recovery-guide.md) for USB setup, a build-only checkpoint, flashing, and restoring stock recovery.

## Requirements

- Bootloader already unlocked (`ro.boot.verifiedbootstate` = `orange`)
- Rooted with [Magisk](https://github.com/topjohnwu/Magisk); the scripts use
  the `magiskboot`, `magiskpolicy` and `busybox` that Magisk installs in
  `/data/adb/magisk`
- `adb` on your computer, device booted into normal Android with USB debugging on

- Bash and `sha256sum` on the host
- Python 3 and OpenSSL on the host if using `sideload-enable` or signing packages

Image repacking runs on the device.

## Usage

```sh
./jarvis2-recovery.sh build     # back up stock, build patched image, flash nothing
./jarvis2-recovery.sh flash     # build, then write it to the active slot
./jarvis2-recovery.sh status    # is the partition stock or patched?
./jarvis2-recovery.sh restore   # put the stock vendor_boot back
```

Set `ADB_SERIAL=<serial>` if more than one device is attached.

After `flash`:

```sh
adb reboot recovery
adb shell id          # uid=0(root) ... context=u:r:shell:s0
adb reboot            # back to Android
```

`build` saves the stock image to `backup/` and the patched one to `out/`.
**Copy `backup/` somewhere safe.** A second copy stays on the device in
`/data/local/tmp/jarvis2-recovery/stock.img`.

## What it changes

On this device recovery is not a partition. It is a second ramdisk fragment
(named `recovery`) inside `vendor_boot` (boot header v4, lz4-legacy), next to
the fragment used for normal boot. Only the recovery fragment is modified:

| File in recovery ramdisk | Change | Why |
| --- | --- | --- |
| `prop.default` | `ro.secure=0`, `ro.adb.secure=0`, `ro.debuggable=1` | adbd starts in recovery, keeps root, skips the RSA prompt |
| `system/etc/init/hw/init.rc` | adbd `--root_seclabel=u:r:su:s0` → `u:r:adbd:s0` | user builds have no `su` SELinux domain; adbd would abort |
| `sepolicy` | `permissive adbd`, `permissive shell` | lets the root shell read and write block devices |
| `system/bin/busybox`, `system/bin/magiskboot` | added | tools for working inside recovery |
| `system/etc/security/otacerts.zip` | *(only with `sideload-enable`)* your cert added next to the stock one | lets your self-signed zips install, OTAs still verify |

Before anything is written, `device/build.sh` unpacks the repacked image again
and checks that the normal-boot ramdisk, the DTB, the bootconfig and the header
are byte-identical to stock, and that the image size is unchanged. `flash`
reads the partition back and compares its SHA-256 with the built image.

## Installing packages signed with your own key

Stock recovery only installs zips signed by the manufacturer. `sideload-enable`
adds **your own** signing key to recovery's `otacerts.zip` (keeping the stock
certs, so official OTAs still verify), then you sign zips with that key:

```sh
./jarvis2-recovery.sh sideload-enable          # generates sideload-key/, flashes
# then, for any zip you want to install:
tools/sign-zip.py in.zip out.zip \
    --key sideload-key/key.pem --cert sideload-key/cert.pem
adb reboot sideload && adb sideload out.zip
```

`sideload-key/key.pem` is your private key — keep it; anyone with it can sign
zips your box will trust. It is git-ignored. The signing uses the AOSP
whole-file (OTA) signature format that `otautil/verifier.cpp` checks; no part of
recovery's verification is disabled.

## Safety

- Only `vendor_boot` of the active slot is written. The bootloader, `boot`,
  `init_boot` and `vbmeta` are never touched.
- The image is written from Android with root (`cat > /dev/block/by-name/...`),
  so fastboot is not needed.
- If recovery fails to start, power-cycle the box. It boots normal Android,
  where `./jarvis2-recovery.sh restore` puts the stock image back.
- Keep each stock backup labeled with its firmware build and slot. Before
  restoring, confirm the backup matches the build and active slot. The restore
  command can reuse the cached device copy.
- After an OTA, obtain a fresh stock image for the new build and active slot
  before rebuilding. Do not reuse a cached image from the previous build.
- Flashing boot images always carries some risk. You do this at your own risk.

## Tested on

| Device | Build | Slot | Result |
| --- | --- | --- | --- |
| onn 4K Pro (`jarvis2`) | `URO3.260203.035.A1.15640252`, Magisk 30.7 | `_b` | recovery root shell works, normal boot unaffected |

On that build the patched image is reproducible:
`sha256 e769d966720847f42be5a6fbfaa8a73a888b606b94c0835339a37e98301a82cb`.

Firmware images are not included in this repo; the scripts build from the
image on your own device.

## Experimental standalone recovery

A separate [RAM recovery prototype](experimental/ram-recovery/README.md) adds
key-only SSH, diagnostics and read-only partition backups. It builds a temporary
boot image and does not modify this stock-recovery patcher. Hardware boot
validation of that prototype is pending.

## License

MIT, see [LICENSE](LICENSE).
