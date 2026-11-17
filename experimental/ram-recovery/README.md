# Jarvis2 RAM Recovery 0.1 — experimental

A standalone Linux recovery prototype for the onn jarvis2. It uses your stock
kernel, device tree and modules, and an Alpine/BusyBox userspace in RAM. It is
separate from the stock-recovery patcher in the repository root.

**This prototype has not yet been boot-tested on hardware.** The boot v2 layout
and stock kernel/DTB have worked in earlier RAM Linux experiments. That does not
validate this new init script, module subset, DHCP startup or SSH service.

## Current scope

- Ethernet DHCP and public-key-only SSH on port 22.
- Internal eMMC block devices set read-only before SSH starts.
- Partition inventory, SHA-256 hashes and raw backup streams to your computer.
- No Android filesystem mounts, restore, wipe, repair or flashing operations.
- Logs and generated SSH host keys stay in RAM.

Read-only block flags prevent accidental writes; a root shell can undo them.
Encrypted userdata is backed up as encrypted raw blocks, not decrypted files.
Only partition labels exposed through kernel sysfs are accepted. If the driver
omits a label, the backup command refuses it rather than guessing a device path.

## Build inputs

Use a Linux host with Python 3. Obtain these files from **your own matching
firmware build**:

1. Stock `boot` v4 and `vendor_boot` v4 images.
2. An ARM64 Alpine root filesystem with `alpine-baselayout`, `busybox` and
   `dropbear` installed. The development artifact used Alpine 3.24 packages.
   Do not use a mounted/live root filesystem or one containing personal files.
3. The modules listed in `modules.load`, from the same running kernel. They may
   come from both the vendor ramdisk and vendor/system module partitions. Put
   them together in one directory. This recovery uses unmodified stock modules.
4. Your Ed25519 SSH **public** key (`ssh-keygen -t ed25519` can create a pair).
   Keep the private key on your computer.

For example, after preparing the inputs:

```sh
python3 build.py \
  --boot /path/to/stock-boot.img \
  --vendor-boot /path/to/stock-vendor_boot.img \
  --runtime /path/to/alpine-aarch64-root \
  --modules /path/to/matching-modules \
  --modules-load modules.load \
  --authorized-key /path/to/id_ed25519.pub \
  --output /path/to/new-output-directory
```

The builder reads files and writes a new output directory; it does not call ADB
or fastboot. Reading a root-owned Alpine filesystem may require running the
builder with sudo. The output contains the image, compressed initramfs and a
manifest of input/output hashes. Builds normalize archive ownership and timestamps.
No firmware or SSH private keys are distributed in this source repository.

## Boot and connect — pending hardware validation

The bootloader must already be unlocked. Connect Ethernet and the computer USB
cable, then enter fastboot using your established procedure. Select the exact
serial and use **boot**, not flash:

```sh
fastboot -s YOUR_DEVICE_SERIAL boot /path/to/jarvis2-ram-recovery.img
```

Find the device's DHCP address on your network, then:

```sh
ssh -i /path/to/id_ed25519 root@DEVICE_IP recoveryctl status
ssh -i /path/to/id_ed25519 root@DEVICE_IP recoveryctl partitions
ssh -i /path/to/id_ed25519 root@DEVICE_IP recoveryctl hash boot_b
ssh -i /path/to/id_ed25519 root@DEVICE_IP recoveryctl backup boot_b > boot_b.img.partial
```

Check SSH's exit status before renaming the `.partial` backup. Compare its local
SHA-256 and size with the remote hash and the inventory's sector count × 512.
Use the actual label from `partitions`, not an assumed active slot. The command
writes binary bytes only to stdout; progress/errors go to stderr. It never writes
a backup into RAM or onto internal storage.

Dropbear generates a new host key each RAM boot. Verify the intended device and
host-key change; do not disable SSH host verification globally. Password login
and SSH forwarding are disabled. USB ADB is not provided by this prototype.

To return to Android:

```sh
ssh -i /path/to/id_ed25519 root@DEVICE_IP recoveryctl reboot
```

Startup failures should return to Android after five minutes (earlier if storage
protection cannot be verified). This is a userspace timeout, **not a hardware
watchdog**: a stalled kernel still requires a power cycle. Successful SSH startup
keeps recovery running until you reboot it. A successful build is not a guarantee
that networking, storage discovery or that timeout will work on the device.

## Verification

```sh
python3 -m unittest discover -s tests -v
sh -n init recoveryctl
```

The partition fixtures require root plus permission to create an inert block
node (`CAP_MKNOD`); run the suite with sudo on a suitable Linux host to exercise
those tests. They mock blockdev/dd/hash and never access real disks. Running as
an ordinary user skips those cases. A restricted container may deny mknod even
with sudo. The boot packer tests reject truncated and incompatible headers and
check payload preservation, image hash, padding and size limits. Archive/key tests
check reproducibility, newc layout and malformed or multiple SSH public keys.
