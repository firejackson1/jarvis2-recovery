"""Exercise the actual shell utility with a synthetic sysfs and inert block node.

Run as root for mknod; dd/hash/blockdev are controlled fixture commands. No real
block device is accessed. Non-root runs skip these fixture tests.
"""
from pathlib import Path
import os
import stat
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).parents[1] / 'recoveryctl'

@unittest.skipUnless(os.geteuid() == 0, 'mknod fixtures require root')
class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.sys = self.root / 'sys'
        self.dev = self.root / 'dev'
        self.mock = self.root / 'bin'
        for p in (self.sys, self.dev, self.mock): p.mkdir()
        disk = self.sys / 'class/block/mmcblk0/device'
        disk.mkdir(parents=True)
        (disk / 'type').write_text('MMC\n')
        self.partition('mmcblk0p5', 'boot_b')
        self.ro = self.root / 'ro'
        self.ro.write_text('1\n')
        self.command('blockdev', f'cat "{self.ro}"')
        self.command('dd', 'printf "BACKUP:%s\\n" "$*"')
        self.command('sha256sum', 'printf "HASH:%s\\n" "$*"')
        self.script = self.root / 'recoveryctl'
        self.script.write_text(SOURCE.read_text().replace('SYS=/sys', f'SYS={self.sys}')
                               .replace('DEV=/dev', f'DEV={self.dev}'))

    def command(self, name, body):
        p = self.mock / name
        p.write_text('#!/bin/sh\n' + body + '\n')
        p.chmod(0o755)

    def partition(self, node, name):
        p = self.sys / 'class/block' / node
        p.mkdir(parents=True)
        (p / 'partition').write_text('5\n')
        (p / 'size').write_text('131072\n')
        (p / 'uevent').write_text(f'DEVNAME={node}\nPARTNAME={name}\n')
        os.mknod(self.dev / node, stat.S_IFBLK | 0o600, os.makedev(240, 0))

    def runctl(self, *args):
        return subprocess.run(['/bin/sh', str(self.script), *args], text=True,
                              capture_output=True, env={**os.environ,
                              'PATH': f'{self.mock}:/usr/bin:/bin'})

    def test_backup_only_readonly_internal_partition(self):
        p = self.runctl('backup', 'boot_b')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn(f'BACKUP:if={self.dev}/mmcblk0p5', p.stdout)
        self.assertNotIn('of=', p.stdout)
        self.ro.write_text('0\n')
        p = self.runctl('backup', 'boot_b')
        self.assertNotEqual(p.returncode, 0)
        self.assertNotIn('BACKUP:', p.stdout)

    def test_rejects_missing_ambiguous_or_unsafe_names(self):
        for name in ('../boot_b', '/dev/mmcblk0p5', 'missing', '', 'boot_b; reboot'):
            self.assertNotEqual(self.runctl('backup', name).returncode, 0, name)
        self.partition('mmcblk0p6', 'boot_b')
        self.assertNotEqual(self.runctl('backup', 'boot_b').returncode, 0)

    def test_excludes_sd_and_nonblock_nodes(self):
        (self.sys / 'class/block/mmcblk0/device/type').write_text('SD\n')
        self.assertNotEqual(self.runctl('backup', 'boot_b').returncode, 0)
        (self.sys / 'class/block/mmcblk0/device/type').write_text('MMC\n')
        (self.dev / 'mmcblk0p5').unlink()
        (self.dev / 'mmcblk0p5').write_text('not a block device')
        self.assertNotEqual(self.runctl('backup', 'boot_b').returncode, 0)

    def test_inventory_hash_and_unknown_operation(self):
        p = self.runctl('partitions')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn('boot_b', p.stdout)
        p = self.runctl('hash', 'boot_b')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn('HASH:', p.stdout)
        self.assertNotEqual(self.runctl('flash', 'boot_b').returncode, 0)
        self.assertNotEqual(self.runctl('backup', 'boot_b', 'extra').returncode, 0)

if __name__ == '__main__': unittest.main()
