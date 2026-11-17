#!/usr/bin/env python3
"""Pack an experimental RAM boot v2 image from the owner's stock v4 images.

Does not invoke adb/fastboot or access any block device. No firmware is included.
"""
import argparse
import hashlib
from pathlib import Path
import struct


def aligned(size, page):
    return (size + page - 1) // page * page


def build_image(boot, vendor, ramdisk, *, limit=128 * 1024 * 1024):
    if len(boot) < 1584 or boot[:8] != b'ANDROID!':
        raise ValueError('expected a complete Android boot v4 header')
    if struct.unpack_from('<I', boot, 40)[0] != 4:
        raise ValueError('only stock boot header v4 is supported')
    kernel_size, _, os_version, header_size = struct.unpack_from('<4I', boot, 8)
    if header_size != 1584 or not kernel_size or len(boot) < 4096 + kernel_size:
        raise ValueError('invalid or truncated stock boot image')
    kernel = boot[4096:4096 + kernel_size]
    if len(vendor) < 2128 or vendor[:8] != b'VNDRBOOT':
        raise ValueError('expected a complete vendor_boot v4 header')
    version, page, kernel_addr, ramdisk_addr, vendor_size = struct.unpack_from('<5I', vendor, 8)
    vendor_header_size, dtb_size, dtb_addr = struct.unpack_from('<IIQ', vendor, 2096)
    if version != 4 or page not in (2048, 4096) or vendor_header_size != 2128:
        raise ValueError('unsupported vendor_boot header or page size')
    dtb_offset = aligned(vendor_header_size, page) + aligned(vendor_size, page)
    if dtb_size < 40 or dtb_offset + dtb_size > len(vendor):
        raise ValueError('invalid or truncated vendor DTB')
    dtb = vendor[dtb_offset:dtb_offset + dtb_size]
    magic, total = struct.unpack_from('>II', dtb)
    if magic != 0xd00dfeed or not 40 <= total <= dtb_size:
        raise ValueError('invalid flattened device tree')
    if not ramdisk:
        raise ValueError('ramdisk must not be empty')
    output_page = 2048  # Validated on jarvis2 via fastboot boot.
    size = output_page + sum(aligned(len(x), output_page) for x in (kernel, ramdisk, dtb))
    if size > limit:
        raise ValueError(f'image size {size} exceeds fastboot RAM limit {limit}')
    header = bytearray(output_page)
    header[:8] = b'ANDROID!'
    tags_addr = struct.unpack_from('<I', vendor, 2076)[0]
    struct.pack_into('<10I', header, 8, kernel_size, kernel_addr, len(ramdisk),
                     ramdisk_addr, 0, 0, tags_addr, output_page, 2, os_version)
    header[48:64] = b'jarvis2-ram'.ljust(16, b'\0')
    cmdline = b'rdinit=/ramboot-init panic=5'
    header[64:64 + len(cmdline)] = cmdline
    struct.pack_into('<IQIIQ', header, 1632, 0, 0, 1660, dtb_size, dtb_addr)
    digest = hashlib.sha1()
    for data in (kernel, ramdisk, b'', b'', dtb):
        digest.update(data)
        digest.update(struct.pack('<I', len(data)))
    header[576:596] = digest.digest()
    return bytes(header) + b''.join(x + bytes(-len(x) % output_page)
                                    for x in (kernel, ramdisk, dtb))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--boot', type=Path, required=True)
    p.add_argument('--vendor-boot', type=Path, required=True)
    p.add_argument('--ramdisk', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    try:
        image = build_image(args.boot.read_bytes(), args.vendor_boot.read_bytes(),
                            args.ramdisk.read_bytes())
        with args.output.open('xb') as f:
            f.write(image)
    except (OSError, ValueError) as e:
        p.exit(1, f'{e}\n')
    print(f'{hashlib.sha256(image).hexdigest()}  {args.output} ({len(image)} bytes)')


if __name__ == '__main__':
    main()
