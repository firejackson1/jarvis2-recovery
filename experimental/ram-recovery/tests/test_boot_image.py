import importlib.util
from pathlib import Path
import hashlib
import struct
import unittest

MODULE = Path(__file__).parents[1] / 'boot_image.py'
spec = importlib.util.spec_from_file_location('boot_image', MODULE)
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)

def fixture():
    kernel = b'K' * 5001
    dtb = struct.pack('>II', 0xd00dfeed, 40) + bytes(32)
    boot = bytearray(4096)
    boot[:8] = b'ANDROID!'
    struct.pack_into('<4I', boot, 8, len(kernel), 0, 0, 1584)
    struct.pack_into('<I', boot, 40, 4)
    vendor = bytearray(4096)
    vendor[:8] = b'VNDRBOOT'
    struct.pack_into('<5I', vendor, 8, 4, 2048, 0x2080000, 0x1000000, 10)
    struct.pack_into('<I', vendor, 2076, 0x100)
    struct.pack_into('<IIQ', vendor, 2096, 2128, len(dtb), 0x1000000)
    vendor += bytes(2048) + dtb
    return bytes(boot) + kernel, bytes(vendor), kernel, dtb

class BootImageTests(unittest.TestCase):
    def test_roundtrip_preserves_kernel_dtb_and_hash(self):
        boot, vendor, kernel, dtb = fixture()
        ramdisk = b'RAMDISK' * 333
        image = b.build_image(boot, vendor, ramdisk)
        self.assertEqual(image[:8], b'ANDROID!')
        self.assertEqual(struct.unpack_from('<I', image, 40)[0], 2)
        self.assertEqual(image[2048:2048 + len(kernel)], kernel)
        r = 2048 + b.aligned(len(kernel), 2048)
        self.assertEqual(image[r:r + len(ramdisk)], ramdisk)
        d = r + b.aligned(len(ramdisk), 2048)
        self.assertEqual(image[d:d + len(dtb)], dtb)
        digest = hashlib.sha1(b''.join(x + struct.pack('<I', len(x))
                              for x in (kernel, ramdisk, b'', b'', dtb))).digest()
        self.assertEqual(image[576:596], digest)
        self.assertEqual(image[596:608], bytes(12))
        self.assertEqual(len(image) % 2048, 0)
        self.assertEqual(image, b.build_image(boot, vendor, ramdisk))

    def test_rejects_bad_inputs(self):
        boot, vendor, _, _ = fixture()
        cases = [(boot[:100], vendor, b'x'), (boot[:-1], vendor, b'x'),
                 (boot, vendor[:-1], b'x'), (boot, vendor, b''),
                 (b'BADMAGIC' + boot[8:], vendor, b'x')]
        for args in cases:
            with self.subTest(lengths=list(map(len, args))):
                with self.assertRaises(ValueError): b.build_image(*args)
        for offset, value in [(8, 3), (12, 0), (2096, 1), (2100, 0)]:
            v = bytearray(vendor)
            struct.pack_into('<I', v, offset, value)
            with self.subTest(offset=offset):
                with self.assertRaises(ValueError): b.build_image(boot, v, b'x')

    def test_rejects_oversize(self):
        boot, vendor, _, _ = fixture()
        with self.assertRaises(ValueError): b.build_image(boot, vendor, b'x', limit=2048)

if __name__ == '__main__': unittest.main()
