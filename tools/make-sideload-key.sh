#!/usr/bin/env bash
# Generate YOUR OWN signing key + self-signed cert for sideload zips.
# Keep key.pem private; cert.pem is what goes into recovery's otacerts.zip.
set -euo pipefail
OUT=${1:-./sideload-key}
mkdir -p "$OUT"
[ -f "$OUT/key.pem" ] && { echo "$OUT/key.pem exists; refusing to overwrite"; exit 1; }
openssl req -x509 -newkey rsa:2048 -sha256 -days 36500 -nodes \
    -keyout "$OUT/key.pem" -out "$OUT/cert.pem" -subj "/CN=jarvis2-sideload"
chmod 600 "$OUT/key.pem"
echo "wrote $OUT/key.pem (private, keep safe) and $OUT/cert.pem"
