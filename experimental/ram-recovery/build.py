#!/usr/bin/env python3
"""Build RAM recovery from locally supplied firmware, modules and Alpine runtime."""
import argparse
import base64
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import struct
from boot_image import build_image

HERE = Path(__file__).resolve().parent


def public_key(data):
    lines = data.strip().splitlines()
    if len(lines) != 1:
        raise ValueError('supply exactly one OpenSSH Ed25519 public key')
    fields = lines[0].split()
    if len(fields) < 2 or fields[0] != b'ssh-ed25519':
        raise ValueError('only plain ssh-ed25519 public keys are supported')
    try:
        blob = base64.b64decode(fields[1], validate=True)
    except ValueError as e:
        raise ValueError('invalid public key encoding') from e
    expected = struct.pack('>I', 11) + b'ssh-ed25519' + struct.pack('>I', 32)
    if len(blob) != len(expected) + 32 or not blob.startswith(expected):
        raise ValueError('invalid Ed25519 SSH key structure')
    return b' '.join(fields[:2]) + b'\n'


def newc(entries):
    output = bytearray()
    all_entries = sorted(entries.items()) + [('TRAILER!!!', (0, b''))]
    for ino, (name, (mode, data)) in enumerate(all_entries, 1):
        encoded = name.encode() + b'\0'
        values = (ino, mode, 0, 0, 1, 0, len(data), 0, 0, 0, 0, len(encoded), 0)
        output += b'070701' + b''.join(f'{v:08x}'.encode() for v in values)
        output += encoded
        output += bytes(-len(output) % 4)
        output += data
        output += bytes(-len(output) % 4)
    return bytes(output)


def runtime_entries(root):
    entries = {}
    for p in sorted(root.rglob('*')):
        name = p.relative_to(root).as_posix()
        # Runtime pseudo-filesystems must never be copied from the host.
        if name.split('/')[0] in ('dev', 'proc', 'sys', 'run', 'tmp'):
            continue
        if name == 'root/.ssh' or name.startswith('root/.ssh/') or name.startswith('etc/dropbear/'):
            continue
        mode = p.lstat().st_mode
        if stat.S_ISDIR(mode): data = b''
        elif stat.S_ISLNK(mode): data = os.readlink(p).encode()
        elif stat.S_ISREG(mode): data = p.read_bytes()
        else: raise ValueError(f'unsupported special file in runtime: {name}')
        entries[name] = (mode, data)
    for name in ('bin/busybox', 'usr/sbin/dropbear', 'lib/ld-musl-aarch64.so.1',
                 'usr/share/udhcpc/default.script'):
        if name not in entries:
            raise ValueError(f'missing runtime requirement: {name}')
    for name in ('bin/busybox', 'usr/sbin/dropbear'):
        data = entries[name][1]
        if data[:5] != b'\x7fELF\x02' or data[5:6] != b'\x01' or data[18:20] != b'\xb7\x00':
            raise ValueError(f'{name} must be a little-endian AArch64 ELF executable')
    return entries


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for option in ('boot', 'vendor-boot', 'runtime', 'modules', 'modules-load', 'authorized-key', 'output'):
        p.add_argument('--' + option, type=Path, required=True)
    args = p.parse_args()
    try:
        if args.output.exists():
            raise ValueError('output directory must not already exist')
        key = public_key(args.authorized_key.read_bytes())
        entries = runtime_entries(args.runtime)
        modules = [line.strip() for line in args.modules_load.read_text().splitlines() if line.strip()]
        if not modules or len(set(modules)) != len(modules):
            raise ValueError('module list must be nonempty and contain no duplicates')
        for name in modules:
            if not re.fullmatch(r'[A-Za-z0-9_.-]+\.ko', name):
                raise ValueError(f'unsafe module name: {name}')
            data = (args.modules / name).read_bytes()
            if data[:4] != b'\x7fELF' or data[18:20] != b'\xb7\x00':
                raise ValueError(f'module is not AArch64 ELF: {name}')
            entries['lib/modules/' + name] = (0o100644, data)
        for directory in ('dev', 'proc', 'sys', 'run', 'tmp', 'root', 'root/.ssh',
                          'lib/modules', 'usr/local', 'usr/local/bin', 'etc/dropbear'):
            entries[directory] = (0o40700 if directory in ('root', 'root/.ssh', 'etc/dropbear') else 0o40755, b'')
        for name in ('init', 'ramboot-init'):
            entries[name] = (0o100755, (HERE / 'init').read_bytes())
        entries['usr/local/bin/recoveryctl'] = (0o100755, (HERE / 'recoveryctl').read_bytes())
        entries['root/.ssh/authorized_keys'] = (0o100600, key)
        entries['modules.load'] = (0o100644, ('\n'.join(modules) + '\n').encode())
        entries['etc/jarvis-recovery-release'] = (0o100644, b'Jarvis2 RAM Recovery 0.1 experimental\n')
        entries['etc/motd'] = (0o100644, b'Experimental RAM recovery. Run recoveryctl help. Internal eMMC is read-only.\n')
        boot, vendor = args.boot.read_bytes(), args.vendor_boot.read_bytes()
        ramdisk = gzip.compress(newc(entries), compresslevel=9, mtime=0)
        image = build_image(boot, vendor, ramdisk)
        digest = lambda data: hashlib.sha256(data).hexdigest()
        manifest = {'version': '0.1-experimental', 'boot_validated': False,
                    'boot_sha256': digest(boot), 'vendor_boot_sha256': digest(vendor),
                    'authorized_key_sha256': digest(key), 'image_bytes': len(image),
                    'image_sha256': digest(image), 'initramfs_sha256': digest(ramdisk),
                    'modules': {name: digest(entries['lib/modules/' + name][1]) for name in modules}}
        args.output.mkdir(parents=True)
        (args.output / 'jarvis2-ram-recovery.img').write_bytes(image)
        (args.output / 'initramfs.cpio.gz').write_bytes(ramdisk)
        (args.output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        print(json.dumps({k: manifest[k] for k in ('image_bytes', 'image_sha256', 'boot_validated')}, indent=2))
    except (OSError, ValueError) as e:
        p.exit(1, f'{e}\n')


if __name__ == '__main__': main()
