# jarvis2-recovery

Root-adb recovery for the **onn 4K Pro Streaming Device** (codename `jarvis2`,
Amlogic S905X5M, Android 14).

There is no TWRP or other custom recovery for this box. This repo patches the
**stock** recovery so that booting into it gives you a root `adb shell` with no
authorization prompt, plus `busybox` and `magiskboot`. That is enough to dump
and restore partitions and to repair a system that no longer boots.

It is a patched stock recovery, not TWRP: the on-screen menu is unchanged and
`adb sideload` still only accepts zips signed by the manufacturer.

## Requirements

- Bootloader already unlocked (`ro.boot.verifiedbootstate` = `orange`)
- Rooted with [Magisk](https://github.com/topjohnwu/Magisk); the scripts use
  the `magiskboot`, `magiskpolicy` and `busybox` that Magisk installs in
  `/data/adb/magisk`
- `adb` on your computer, device booted into normal Android with USB debugging on

Nothing else is needed on the host. All image work happens on the device.

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

Before anything is written, `device/build.sh` unpacks the repacked image again
and checks that the normal-boot ramdisk, the DTB, the bootconfig and the header
are byte-identical to stock, and that the image size is unchanged. `flash`
reads the partition back and compares its SHA-256 with the built image.

## Safety

- Only `vendor_boot` of the active slot is written. The bootloader, `boot`,
  `init_boot` and `vbmeta` are never touched.
- The image is written from Android with root (`cat > /dev/block/by-name/...`),
  so fastboot is not needed.
- If recovery fails to start, power-cycle the box. It boots normal Android,
  where `./jarvis2-recovery.sh restore` puts the stock image back.
- A system update (OTA) replaces `vendor_boot` and removes the patch. Run
  `flash` again afterwards; it builds from the new stock image.
- Flashing boot images always carries some risk. You do this at your own risk.

## Tested on

| Device | Build | Slot | Result |
| --- | --- | --- | --- |
| onn 4K Pro (`jarvis2`) | `URO3.260203.035.A1.15640252`, Magisk 30.7 | `_b` | recovery root shell works, normal boot unaffected |

On that build the patched image is reproducible:
`sha256 e769d966720847f42be5a6fbfaa8a73a888b606b94c0835339a37e98301a82cb`.

Firmware images are not included in this repo; the scripts build from the
image on your own device.

## License

MIT, see [LICENSE](LICENSE).
