# RAM recovery prototype design

Build a standalone recovery for jarvis2 using the owner's stock kernel and DTB,
a minimal Alpine/BusyBox initramfs, and Dropbear with a supplied public SSH key.
Boot via `fastboot boot` only. Never flash, change slots, save bootloader settings,
or mount Android filesystems. Set internal eMMC devices read-only before offering
access; this is an accident-prevention measure, not a security boundary for root.

Version 0.1 provides Ethernet DHCP, an SSH shell, partition inventory, hashes,
and binary backup streams to the host. No restore, wipe, package installation,
filesystem repair, decrypted userdata access, or graphical UI in this prototype.
A network startup failure triggers a timed return to Android. All logs and keys
created at runtime live in RAM. Require a supplied SSH public key at build time;
never ship private keys or firmware in source control.

Hardware boot validation is pending. Host tests must be reported as such.
