from pathlib import Path
import base64
import importlib.util
import struct
import sys
import unittest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))
import build

class BuildTests(unittest.TestCase):
    def test_public_key_validation(self):
        field = lambda x: struct.pack('>I', len(x)) + x
        blob = field(b'ssh-ed25519') + field(bytes(range(32)))
        key = b'ssh-ed25519 ' + base64.b64encode(blob) + b' optional-comment\n'
        self.assertEqual(build.public_key(key), key.split(b' optional')[0] + b'\n')
        for bad in (b'', b'PRIVATE KEY', key + key,
                    b'ssh-ed25519 eA==', key.replace(b'ssh-ed25519 ', b'ssh-rsa ', 1)):
            with self.subTest(key=bad):
                with self.assertRaises(ValueError): build.public_key(bad)

    def test_newc_roundtrip_independent_parser(self):
        archive = build.newc({'init': (0o100755, b'hello'),
                              'bin': (0o40755, b''),
                              'bin/sh': (0o120777, b'busybox')})
        p, entries = 0, {}
        while True:
            self.assertEqual(archive[p:p+6], b'070701')
            values = [int(archive[p+6+i*8:p+14+i*8], 16) for i in range(13)]
            _, mode, uid, gid, _, mtime, size, _, _, _, _, namesize, _ = values
            self.assertEqual((uid, gid, mtime), (0, 0, 0))
            name = archive[p+110:p+110+namesize-1].decode()
            p = (p + 110 + namesize + 3) & ~3
            data = archive[p:p+size]
            p = (p + size + 3) & ~3
            if name == 'TRAILER!!!': break
            entries[name] = (mode, data)
        self.assertEqual(entries['init'], (0o100755, b'hello'))
        self.assertEqual(entries['bin/sh'], (0o120777, b'busybox'))
        self.assertEqual(archive, build.newc(dict(reversed(list(entries.items())))))

if __name__ == '__main__': unittest.main()
