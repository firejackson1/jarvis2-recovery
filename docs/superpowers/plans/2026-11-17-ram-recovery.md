# RAM Recovery Implementation Plan

> Execute inline with superpowers:executing-plans. Review the finished change separately.

**Goal:** Produce a RAM-only diagnostic recovery image and reusable source tools.
**Architecture:** Stock boot v4 supplies the kernel; stock vendor_boot v4 supplies
DTB and addresses. Package a small initramfs in the known-working legacy boot v2
layout. BusyBox PID1 loads supplied modules, locks eMMC read-only, obtains an
Ethernet lease, and launches key-only Dropbear. A shell command exposes read-only
partition backup operations.
**Tech Stack:** Python standard library, POSIX shell, Alpine BusyBox, Dropbear.
**Spec:** 2026-11-17-ram-recovery-design.md

## Global Constraints

No Android partition writes. No hardware-dependent success claims without boot
validation. No firmware, credentials or personal logs
in this repository. User has delegated design choices and asked to work unattended.

## Review Focus

- Reject truncated or incompatible boot headers before producing output.
- Preserve stock kernel/DTB byte-for-byte and validate legacy image hash.
- Reject partition traversal, ambiguous labels, and non-read-only devices.
- Refuse to build without a valid public key; disable password SSH authentication.
- Clearly identify untested hardware boot and timeout limitations.

## Tasks

- [x] Implement and test boot-v2 packer against synthetic and real stock inputs.
- [x] Implement read-only recovery command with fixture tests for selection/refusal.
- [x] Build minimal keyed runtime, init script and reproducible build instructions.
- [x] Validate archive content, shell syntax, image roundtrip and architecture.
- [x] Review source, package an experimental image, and record hardware limitations.

## Validation record

Nine host tests passed, including all four inert-block-node fixture tests on a
Linux host with CAP_MKNOD. ShellCheck and target BusyBox shell syntax checks passed.
Two builds produced the identical 26,701,824-byte image. Kernel, DTB and load
addresses match the earlier working RAM image. Independent source review found
no confirmed important defects. Actual boot, eMMC flags, Ethernet/SSH and fallback
reboot remain untested on this prototype.
