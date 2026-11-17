#!/usr/bin/env python3
"""Whole-file (OTA) sign a zip so Amlogic/AOSP recovery accepts it via adb sideload.

Matches bootable/recovery/otautil/verifier.cpp verify_file():
the signed region is everything up to (not including) the EOCD 2-byte comment-length
field; the archive comment holds a PKCS#7 (no signed attrs) DER blob followed by a
6-byte footer "(2-byte signature_start) ff ff (2-byte comment_size)".

Needs openssl on PATH. Sign with the key whose cert is in the device's otacerts.zip
(see tools/make-sideload-key.sh and the 'sideload-enable' command).

usage: sign-zip.py <in.zip> <out.zip> --key key.pem --cert cert.pem [--md sha256]
"""
import argparse, struct, subprocess, sys, tempfile, os

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inzip"); ap.add_argument("outzip")
    ap.add_argument("--key", required=True); ap.add_argument("--cert", required=True)
    ap.add_argument("--md", default="sha256", choices=["sha256", "sha1"])
    a = ap.parse_args()

    f = open(a.inzip, "rb").read()
    eo = f.rfind(b"PK\x05\x06")
    if eo < 0:
        sys.exit("not a zip: no EOCD record")
    if struct.unpack("<H", f[eo+20:eo+22])[0] != 0:
        sys.exit("input zip already has an archive comment; re-zip without one")
    signed = f[:eo+20]                       # up to the comment-length field

    with tempfile.TemporaryDirectory() as t:
        sp = os.path.join(t, "signed.bin"); p7 = os.path.join(t, "sig.p7")
        open(sp, "wb").write(signed)
        subprocess.check_call(["openssl", "cms", "-sign", "-binary", "-noattr",
            "-nocerts", "-md", a.md, "-signer", a.cert, "-inkey", a.key,
            "-outform", "DER", "-in", sp, "-out", p7])
        sig = open(p7, "rb").read()

    csize = len(sig) + 6
    if csize > 0xffff:
        sys.exit("signature too large for a zip comment")
    footer = struct.pack("<H", csize) + b"\xff\xff" + struct.pack("<H", csize)
    eocd = bytearray(f[eo:eo+22]); eocd[20:22] = struct.pack("<H", csize)
    open(a.outzip, "wb").write(f[:eo] + bytes(eocd) + sig + footer)
    print("signed ->", a.outzip, "(comment %d bytes)" % csize)

if __name__ == "__main__":
    main()
