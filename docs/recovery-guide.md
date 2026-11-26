# Install jarvis2-recovery on the onn 4K Pro
## Reproduction runbook for Linux and Windows 11

**Source revision:** [`cdcdf54f7f987de1215f39e85d55d1324b8835ba`](https://github.com/firejackson1/jarvis2-recovery/tree/cdcdf54f7f987de1215f39e85d55d1324b8835ba). This walkthrough intentionally uses that revision instead of whatever is newest on `main`.

**How to use this guide:** Set up one computer using section 1, then follow sections 2–6 in order. Run one block at a time and check its result before moving on. Do not paste the entire guide into a terminal. The first checkpoint finishes before any boot partition is written.

This installs a modified recovery on an **already bootloader-unlocked, Magisk-rooted** onn 4K Pro with the device codename `jarvis2` (Amlogic S905X5M, Android 14). It does **not** unlock, root, or unbrick a box. You need to be able to boot normal Android. The project reports testing on build `URO3.260203.035.A1.15640252`, Magisk 30.7, slot `_b`. Your active slot can differ; other builds are not verified by that report.

**Read this before flashing:** Modified recovery gives any connected USB host root access without an authorization prompt. Connect it only to a computer you trust. Flashing writes the current slot's `vendor_boot` and can make the device unbootable. Back up anything important, use stable power and a data-capable USB connection, and save the original image off the box before flashing. If you only want to build or inspect the image, stop after step 4.

## 1. Set up the computer

### Option A: Ubuntu or Debian on a Linux PC

In Terminal:

```bash
sudo apt update
sudo apt install -y git adb android-sdk-platform-tools-common coreutils
adb version
```

On other distributions, install Git, Bash, coreutils and ADB through your package manager, or use Google's [Linux SDK Platform-Tools](https://developer.android.com/tools/releases/platform-tools). If the box appears but ADB reports a permissions error, use your distro's Android USB rules and sign out and back in if you added yourself to a device-access group. Don't run the recovery script as root on your PC.

### Option B: Windows 11 with Ubuntu in WSL 2

The repo ships a Bash script, not a native PowerShell installer. This route runs the Linux script and Linux ADB inside Ubuntu. It is based on Microsoft's documented USB passthrough procedure; it has not been hardware-tested for this guide.

1. Open **PowerShell as Administrator** and install Ubuntu and USB passthrough. Restart if prompted. If Ubuntu is already installed, use `wsl -l -v` to check that it says version **2**; skip the install if it's already set up.

   ```powershell
   wsl --install -d Ubuntu
   winget install --interactive --exact dorssel.usbipd-win
   ```

2. Open **Ubuntu** from Start, create the Linux username and password if prompted, and leave its terminal open. Run the Linux install commands above inside Ubuntu. `adb version` should print the ADB version. A path ending in `adb.exe` is the Windows binary; this guide uses Linux `adb` inside Ubuntu.
3. Power on the box normally, enable USB debugging, and connect its USB data connection to the PC. In **Administrator PowerShell**, run `usbipd list`. Identify the box by unplugging and reconnecting its data cable if you're unsure. Replace `4-4` below with the box's actual bus ID.

   ```powershell
   usbipd bind --busid 4-4
   usbipd attach --wsl --busid 4-4
   usbipd list
   ```

   You only need administrator privileges for the bind step. Skip bind if the device is already shared. The device should show as **Attached**. After this, use **Ubuntu** for every `adb` and recovery-script command. If USB drops or the device changes identity when entering recovery or returning to Android, run `usbipd list` again and attach the new entry; bind it first if it isn't shared. See [Microsoft's USB-to-WSL guide](https://learn.microsoft.com/en-us/windows/wsl/connect-usb).

## 2. Verify the box in normal Android

Plug the box in if you haven't already. Allow USB debugging on the TV if prompted. Disconnect other Android devices and close emulators so every command targets this box. In Linux Terminal or Ubuntu on Windows:

On the TV, if Developer options are hidden, open **Settings → System → About** and select **Android TV OS build** seven times. Back out to **System → Developer options** and turn on **USB debugging** if offered. Leave the box on its own power supply and connected to HDMI so you can accept the prompt and see recovery. Before flashing, prove USB ADB works: the box must respond to `adb -d get-state` with `device`. This guide does not depend on Wi-Fi ADB continuing to work in recovery.

```bash
adb devices -l
adb -d get-state
adb shell getprop ro.product.device
adb shell getprop ro.boot.verifiedbootstate
adb shell "su -c 'id -u'"
adb shell getprop ro.build.display.id
adb shell getprop ro.boot.slot_suffix
```

Expected output, in order: one target marked `device`; `device` from the USB-only check; `jarvis2`; `orange`; `0`; your firmware build; and `_a` or `_b`. Approve the Shell root request in Magisk if prompted, then rerun the check. If the device is `unauthorized`, accept the debugging prompt on the TV and rerun `adb devices -l`. If the list is empty, fix the cable, USB connection, or WSL attachment before continuing. If any model, unlock, root or slot check fails, **stop**. Do not use an override. For the first public reproduction, use the reported test build and Magisk version; treat any other configuration as a separate test.

## 3. Download the recovery scripts

In the same Linux or Ubuntu terminal:

```bash
cd ~
git clone https://github.com/firejackson1/jarvis2-recovery.git jarvis2-recovery-cdcdf54
cd jarvis2-recovery-cdcdf54
git checkout --detach cdcdf54f7f987de1215f39e85d55d1324b8835ba
git rev-parse HEAD
unset FORCE STOCK_IMG ADB_SERIAL
bash jarvis2-recovery.sh status
```

The printed commit must equal the full revision above. Record the active partition SHA-256 printed by `status` as your **before** hash. If it says it matches the patched image, stop. These steps assume a first install on a known-stock `vendor_boot` for this build and slot. Matching the before hash proves that the backup is a copy of the current partition, not that a previously modified partition is stock. After an OTA or slot switch, don't reuse the previous stock image. The script can reuse its device-side cache, and `restore` can select a same-slot backup from another build if multiple copies match. Keep backups separated by device, build and slot.

On a fresh device, this revision of `status` may return a nonzero exit code **after** printing the partition hash because there are no cached images yet. That's expected only if it printed the correct build and slot and a full `vendor_boot_a sha256:` or `vendor_boot_b sha256:` line. If there's no hash or you see a preflight error, stop.

## 4. Build without flashing and save the stock image

```bash
bash jarvis2-recovery.sh build
ls -lh backup/ out/
sha256sum backup/*.img
sha256sum out/*.img
bash jarvis2-recovery.sh status
```

In a fresh checkout, expect one image in each folder. For example, on the reported test setup they are `backup/vendor_boot_b-stock-URO3.260203.035.A1.15640252.img` and `out/vendor_boot_b-rootadb-URO3.260203.035.A1.15640252.img`. The stock file hash **and** the new `status` partition hash must both equal the before hash from step 3. That is your no-flash checkpoint. The project publishes this reference patched SHA-256 for its test configuration: `e769d966720847f42be5a6fbfaa8a73a888b606b94c0835339a37e98301a82cb`. If you're reproducing that configuration and the digest differs, stop at build-only rather than assuming the image is equivalent.

Copy the stock image **and its recorded SHA-256** to a second location. On Windows, `explorer.exe .` from Ubuntu opens the working folder, so you can copy it out of WSL. If the build fails, reports reused stock during a fresh first build, says it injected a certificate when you didn't intend to, or produces unexpected names or hashes, **do not flash**. You can stop here and independently reproduce the build without changing the boot partition.

## 5. Flash and test

Still in normal Android, run `adb -d get-state` and `bash jarvis2-recovery.sh status` again. Confirm the same box, build, slot and before hash. Then:

```bash
bash jarvis2-recovery.sh flash
```

This rebuilds, writes the active slot's `vendor_boot`, and verifies the partition by reading it back. **Wait for the write-and-verify success message.** If it reports a read-back mismatch, **do not reboot or unplug**. See step 6, and use only a verified stock backup for this build and slot.

After a successful flash:

```bash
adb reboot recovery
```

Wait for recovery to appear, reattach USB to WSL if needed, and confirm the target before testing:

```bash
adb devices -l
adb shell id
```

Expect `uid=0(root)`. Then return to Android and confirm it boots normally:

```bash
adb reboot
```

Once Android is back and ADB sees it, run `bash jarvis2-recovery.sh status`. It should report a match with the patched image, and its partition SHA-256 should equal the patched hash you recorded in step 4. If it doesn't, record what you saw and don't count the run as a success. Verify normal Android on the TV, not just an ADB connection.

## 6. Restore stock recovery if needed

If recovery fails to start **after a verified write** but Android still boots after a power cycle, return to normal Android and reconnect ADB. If a write verification failed, stay in the running Android session instead of power-cycling.

Recheck the firmware build and slot. The script prefers its cached stock image on the box, so verify that cache against your saved host backup hash before using it:

```bash
adb shell "su -c 'sha256sum /data/local/tmp/jarvis2-recovery/stock.img'"
```

If the cache exists and its hash matches the recorded backup for this exact device, build and slot:

```bash
bash jarvis2-recovery.sh restore
bash jarvis2-recovery.sh status
```

Wait for successful write verification. If the cache is missing, the script can fall back to a host backup, but **only proceed if there is exactly one matching-slot backup in the repo's `backup/` folder and it matches the recorded build and hash**. If the cache exists but is wrong, or Android won't boot, stop. This is not a dead-boot recovery method.

## Reproduction checklist

For each host, record the results below. **Build reproduced** means the expected stock backup exists, the build passed, and the active partition hash did not change. **Install reproduced** additionally means the write verified, recovery returned `uid=0(root)`, and normal Android booted again. **Restore verified** means the restored partition hash matches the original before hash and normal Android boots. On a test box, restore is a separate test; don't assume it passed just because install worked.

| Check | Record |
| --- | --- |
| PC and connection | Linux distribution/version, or Windows version + WSL/Ubuntu and usbipd versions; `adb version` |
| Box | Codename, firmware build, slot and Magisk version (don't share the serial) |
| Source and images | Git commit, before/after-build partition hashes, backup hash, patched hash |
| Hardware results | Flash read-back, recovery `id`, Android boot, restore/hash match if tested |

The repository author reports a successful device test on the configuration at the top. For this guide, the pinned host script's build, flash read-back and restore flow were exercised against simulated ADB with dummy files. That checks the host-side flow, not image repacking, USB passthrough, or booting the box. An independent end-to-end run on Linux and Windows still needs someone with the actual hardware.

## Optional: sideload your own signed test packages

Skip this for a normal recovery install. In Linux or Ubuntu, install `python3` and `openssl` using your package manager. Then, after the same device and backup checks:

```bash
bash jarvis2-recovery.sh sideload-enable
python3 tools/sign-zip.py in.zip out.zip --key sideload-key/key.pem --cert sideload-key/cert.pem
adb reboot sideload
```

**The first command flashes.** It adds a certificate alongside the stock certificates. Keep `sideload-key/key.pem` private. Only use a package you prepared or verified specifically for this device and build. After recovery shows the device in sideload mode (reattach USB on WSL if necessary), run `adb sideload out.zip` and check the result on the recovery screen before rebooting. The script can reuse the generated certificate on later builds from the same device-side work directory; run the verified stock restore if you want stock recovery back.

**References:** [Project README](https://github.com/firejackson1/jarvis2-recovery#readme) · [Host script](https://github.com/firejackson1/jarvis2-recovery/blob/main/jarvis2-recovery.sh) · [ADB documentation](https://developer.android.com/tools/adb) · [Install WSL](https://learn.microsoft.com/en-us/windows/wsl/install)
