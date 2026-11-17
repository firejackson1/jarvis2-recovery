#!/usr/bin/env python3
"""Build a recovery otacerts.zip = stock certs (kept) + your sideload cert (added).

usage: build-otacerts.py <stock-otacerts.zip> <your-cert.pem> <out-otacerts.zip>
Keeping the stock certs means official OTAs still verify; adding yours lets your
own signed zips verify too.
"""
import sys, zipfile
if len(sys.argv) != 4:
    sys.exit(__doc__)
stock, cert, out = sys.argv[1:]
zi = zipfile.ZipFile(stock)
zo = zipfile.ZipFile(out, "w", zipfile.ZIP_STORED)
for n in zi.namelist():
    zo.writestr(n, zi.read(n))
if "sideload.x509.pem" in zi.namelist():
    sys.exit("stock already contains sideload.x509.pem")
zo.write(cert, "sideload.x509.pem")
zo.close()
print("wrote", out, "->", zipfile.ZipFile(out).namelist())
